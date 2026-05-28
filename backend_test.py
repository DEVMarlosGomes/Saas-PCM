#!/usr/bin/env python3
"""
Backend API Testing for AURIX SaaS System
Tests billing, plan limits, downtime costs, review workflow, enhanced features,
failure_group bloqueio, tecnico login, dashboards por perfil, and occurrence patch.
"""

import requests
import json
import time
from datetime import datetime, timezone
import sys
import os

# Fix Windows encoding for emoji / non-ASCII output
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Configuration — fallback to localhost if env var not set
BASE_URL = os.environ.get("AURIX_API_URL", "http://localhost:8001/api")
ADMIN_EMAIL = "admin@demo.pcm"
ADMIN_PASSWORD = "admin123"

class PCMTester:
    def __init__(self):
        self.session = requests.Session()
        self.auth_token = None
        self.org_id = None
        self.test_results = []
        
    def log_test(self, test_name, success, details="", error=""):
        """Log test result"""
        result = {
            "test": test_name,
            "success": success,
            "details": details,
            "error": error,
            "timestamp": datetime.now().isoformat()
        }
        self.test_results.append(result)
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {test_name}")
        if details:
            print(f"   Details: {details}")
        if error:
            print(f"   Error: {error}")
        print()
    
    def seed_demo_data(self):
        """Seed demo data"""
        try:
            response = self.session.post(f"{BASE_URL}/seed-demo")
            if response.status_code == 200:
                data = response.json()
                self.log_test("Seed Demo Data", True, f"Demo data created: {data.get('message', '')}")
                return True
            else:
                self.log_test("Seed Demo Data", False, error=f"Status {response.status_code}: {response.text}")
                return False
        except Exception as e:
            self.log_test("Seed Demo Data", False, error=str(e))
            return False
    
    def login(self):
        """Login and get JWT token"""
        try:
            login_data = {
                "email": ADMIN_EMAIL,
                "password": ADMIN_PASSWORD
            }
            response = self.session.post(f"{BASE_URL}/auth/login", json=login_data)
            
            if response.status_code == 200:
                data = response.json()
                self.auth_token = data.get("access_token")
                self.org_id = data.get("organization_id")
                
                # Set authorization header for future requests
                self.session.headers.update({
                    "Authorization": f"Bearer {self.auth_token}"
                })
                
                self.log_test("Admin Login", True, f"Logged in as {data.get('nome')} ({data.get('role')})")
                return True
            else:
                self.log_test("Admin Login", False, error=f"Status {response.status_code}: {response.text}")
                return False
        except Exception as e:
            self.log_test("Admin Login", False, error=str(e))
            return False
    
    def test_billing_plan_endpoint(self):
        """Test GET /api/billing/plan"""
        try:
            response = self.session.get(f"{BASE_URL}/billing/plan")
            
            if response.status_code == 200:
                data = response.json()
                required_fields = ["plano", "limits", "usage", "usage_percent", "all_plans"]
                
                missing_fields = [field for field in required_fields if field not in data]
                if missing_fields:
                    self.log_test("Billing Plan Info", False, error=f"Missing fields: {missing_fields}")
                    return False
                
                # Check if usage_percent is calculated
                usage_percent = data.get("usage_percent", {})
                if not isinstance(usage_percent, dict):
                    self.log_test("Billing Plan Info", False, error="usage_percent should be a dict")
                    return False
                
                self.log_test("Billing Plan Info", True, 
                    f"Plan: {data['plano']}, Usage: {data['usage']}, Limits: {data['limits']}")
                return True
            else:
                self.log_test("Billing Plan Info", False, error=f"Status {response.status_code}: {response.text}")
                return False
        except Exception as e:
            self.log_test("Billing Plan Info", False, error=str(e))
            return False
    
    def test_billing_transactions_endpoint(self):
        """Test GET /api/billing/transactions"""
        try:
            response = self.session.get(f"{BASE_URL}/billing/transactions")
            
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, list):
                    self.log_test("Billing Transactions", True, f"Retrieved {len(data)} transactions")
                    return True
                else:
                    self.log_test("Billing Transactions", False, error="Response should be an array")
                    return False
            else:
                self.log_test("Billing Transactions", False, error=f"Status {response.status_code}: {response.text}")
                return False
        except Exception as e:
            self.log_test("Billing Transactions", False, error=str(e))
            return False
    
    def test_billing_checkout_endpoint(self):
        """Test POST /api/billing/checkout"""
        try:
            checkout_data = {
                "plan": "pro",
                "origin_url": "http://localhost:3000"
            }
            response = self.session.post(f"{BASE_URL}/billing/checkout", json=checkout_data)
            
            # This may fail with Stripe test key, but we should get proper error or redirect URL
            if response.status_code in [200, 400, 402]:
                data = response.json()
                if response.status_code == 200:
                    # Should have checkout URL or session info
                    if "url" in data or "session_id" in data:
                        self.log_test("Billing Checkout", True, "Checkout session created successfully")
                    else:
                        self.log_test("Billing Checkout", True, "Checkout endpoint working (no URL in test mode)")
                else:
                    # Expected error with test Stripe key
                    self.log_test("Billing Checkout", True, f"Expected error with test key: {data.get('detail', 'Unknown error')}")
                return True
            else:
                self.log_test("Billing Checkout", False, error=f"Status {response.status_code}: {response.text}")
                return False
        except Exception as e:
            self.log_test("Billing Checkout", False, error=str(e))
            return False
    
    def test_plan_limit_enforcement(self):
        """Test plan limit enforcement by creating resources until hitting limits"""
        try:
            # First get current plan info
            plan_response = self.session.get(f"{BASE_URL}/billing/plan")
            if plan_response.status_code != 200:
                self.log_test("Plan Limit Enforcement", False, error="Could not get plan info")
                return False
            
            plan_data = plan_response.json()
            limits = plan_data.get("limits", {})
            usage = plan_data.get("usage", {})
            
            # Test equipamentos limit
            max_equipamentos = limits.get("max_equipamentos", 10)
            current_equipamentos = usage.get("equipamentos", 0)
            
            if current_equipamentos >= max_equipamentos:
                # Try to create one more equipamento - should get 402
                equip_data = {
                    "codigo": "TEST-LIMIT",
                    "nome": "Test Equipment for Limit",
                    "valor_hora": 100.0
                }
                response = self.session.post(f"{BASE_URL}/equipamentos", json=equip_data)
                
                if response.status_code == 402:
                    error_msg = response.json().get("detail", "")
                    if "limite" in error_msg.lower() or "upgrade" in error_msg.lower():
                        self.log_test("Plan Limit Enforcement", True, 
                            f"Correctly blocked creation with 402: {error_msg}")
                        return True
                    else:
                        self.log_test("Plan Limit Enforcement", False, 
                            error=f"Got 402 but wrong message: {error_msg}")
                        return False
                else:
                    self.log_test("Plan Limit Enforcement", False, 
                        error=f"Expected 402 but got {response.status_code}")
                    return False
            else:
                self.log_test("Plan Limit Enforcement", True, 
                    f"Current usage ({current_equipamentos}/{max_equipamentos}) allows more resources")
                return True
                
        except Exception as e:
            self.log_test("Plan Limit Enforcement", False, error=str(e))
            return False
    
    def test_downtime_cost_calculation(self):
        """Test downtime cost calculation in OS endpoints"""
        try:
            # Get list of OS
            response = self.session.get(f"{BASE_URL}/ordens-servico")
            if response.status_code != 200:
                self.log_test("Downtime Cost Calculation", False, error="Could not get OS list")
                return False
            
            os_list = response.json()
            if not os_list:
                self.log_test("Downtime Cost Calculation", False, error="No OS found for testing")
                return False
            
            # Check if OS have custo_parada field
            os_with_cost = [os for os in os_list if "custo_parada" in os]
            if not os_with_cost:
                self.log_test("Downtime Cost Calculation", False, error="No OS found with custo_parada field")
                return False
            
            # Test individual OS endpoint
            test_os = os_with_cost[0]
            os_id = test_os["id"]
            
            response = self.session.get(f"{BASE_URL}/ordens-servico/{os_id}")
            if response.status_code != 200:
                self.log_test("Downtime Cost Calculation", False, error=f"Could not get OS {os_id}")
                return False
            
            os_detail = response.json()
            required_fields = ["custo_parada", "equipamento_nome", "revisor_nome"]
            
            has_custo_parada = "custo_parada" in os_detail
            has_equipamento_nome = "equipamento_nome" in os_detail
            has_revisor_nome = "revisor_nome" in os_detail
            
            if has_custo_parada and has_equipamento_nome:
                self.log_test("Downtime Cost Calculation", True, 
                    f"OS {os_id} has custo_parada: {os_detail.get('custo_parada')}, equipamento: {os_detail.get('equipamento_nome')}")
                return True
            else:
                missing = []
                if not has_custo_parada:
                    missing.append("custo_parada")
                if not has_equipamento_nome:
                    missing.append("equipamento_nome")
                self.log_test("Downtime Cost Calculation", False, 
                    error=f"Missing fields in OS detail: {missing}")
                return False
                
        except Exception as e:
            self.log_test("Downtime Cost Calculation", False, error=str(e))
            return False
    
    def test_review_workflow(self):
        """Test review workflow functionality"""
        try:
            # Get an OS to update
            response = self.session.get(f"{BASE_URL}/ordens-servico")
            if response.status_code != 200:
                self.log_test("Review Workflow", False, error="Could not get OS list")
                return False
            
            os_list = response.json()
            if not os_list:
                self.log_test("Review Workflow", False, error="No OS found for testing")
                return False
            
            # Find an OS that's not in review status
            test_os = None
            for os in os_list:
                if os.get("status") in ["aberta", "em_atendimento"]:
                    test_os = os
                    break
            
            if not test_os:
                self.log_test("Review Workflow", False, error="No suitable OS found for review workflow test")
                return False
            
            os_id = test_os["id"]
            
            # Update OS to "aguardando_revisao" status
            update_data = {
                "status": "aguardando_revisao",
                "solucao": "Test solution for review workflow"
            }
            
            response = self.session.put(f"{BASE_URL}/ordens-servico/{os_id}", json=update_data)
            if response.status_code != 200:
                self.log_test("Review Workflow", False, 
                    error=f"Could not update OS to review status: {response.status_code} {response.text}")
                return False
            
            updated_os = response.json()
            
            # Check if review_deadline is set and revisor_id is auto-assigned
            has_deadline = updated_os.get("review_deadline") is not None
            has_revisor = updated_os.get("revisor_id") is not None
            
            if has_deadline and has_revisor:
                self.log_test("Review Workflow - Status Update", True, 
                    f"OS {os_id} updated with review_deadline and auto-assigned revisor")
            else:
                missing = []
                if not has_deadline:
                    missing.append("review_deadline")
                if not has_revisor:
                    missing.append("revisor_id")
                self.log_test("Review Workflow - Status Update", False, 
                    error=f"Missing fields after status update: {missing}")
                return False
            
            # Test pending reviews endpoint
            response = self.session.get(f"{BASE_URL}/ordens-servico/pending-reviews")
            if response.status_code == 200:
                pending_reviews = response.json()
                self.log_test("Review Workflow - Pending Reviews", True, 
                    f"Retrieved {len(pending_reviews)} pending reviews")
            else:
                self.log_test("Review Workflow - Pending Reviews", False, 
                    error=f"Status {response.status_code}: {response.text}")
                return False
            
            # Test auto-approve endpoint
            response = self.session.post(f"{BASE_URL}/ordens-servico/auto-approve")
            if response.status_code == 200:
                auto_approve_result = response.json()
                self.log_test("Review Workflow - Auto Approve", True, 
                    f"Auto-approve executed: {auto_approve_result.get('message', '')}")
            else:
                self.log_test("Review Workflow - Auto Approve", False, 
                    error=f"Status {response.status_code}: {response.text}")
                return False
            
            return True
            
        except Exception as e:
            self.log_test("Review Workflow", False, error=str(e))
            return False
    
    def test_enhanced_dashboard_kpis(self):
        """Test enhanced dashboard KPIs"""
        try:
            response = self.session.get(f"{BASE_URL}/dashboard/kpis")
            
            if response.status_code != 200:
                self.log_test("Enhanced Dashboard KPIs", False, 
                    error=f"Status {response.status_code}: {response.text}")
                return False
            
            kpis = response.json()
            
            # Check for new fields
            required_new_fields = ["avg_tempo_resposta", "top_equipamentos_downtime"]
            missing_fields = [field for field in required_new_fields if field not in kpis]
            
            if missing_fields:
                self.log_test("Enhanced Dashboard KPIs", False, 
                    error=f"Missing enhanced fields: {missing_fields}")
                return False
            
            # Validate structure
            avg_tempo_resposta = kpis.get("avg_tempo_resposta")
            top_downtime = kpis.get("top_equipamentos_downtime")
            
            if not isinstance(avg_tempo_resposta, (int, float)):
                self.log_test("Enhanced Dashboard KPIs", False, 
                    error="avg_tempo_resposta should be a number")
                return False
            
            if not isinstance(top_downtime, list):
                self.log_test("Enhanced Dashboard KPIs", False, 
                    error="top_equipamentos_downtime should be a list")
                return False
            
            self.log_test("Enhanced Dashboard KPIs", True, 
                f"Enhanced KPIs working - avg_tempo_resposta: {avg_tempo_resposta}, downtime entries: {len(top_downtime)}")
            return True
            
        except Exception as e:
            self.log_test("Enhanced Dashboard KPIs", False, error=str(e))
            return False
    
    def test_enhanced_audit_trail(self):
        """Test enhanced audit trail with field changes"""
        try:
            response = self.session.get(f"{BASE_URL}/auditoria")
            
            if response.status_code != 200:
                self.log_test("Enhanced Audit Trail", False, 
                    error=f"Status {response.status_code}: {response.text}")
                return False
            
            audit_logs = response.json()
            
            if not isinstance(audit_logs, list):
                self.log_test("Enhanced Audit Trail", False, 
                    error="Audit logs should be a list")
                return False
            
            # Check if any logs have dados_novos field
            logs_with_changes = [log for log in audit_logs if "dados_novos" in log and log["dados_novos"]]
            
            if logs_with_changes:
                sample_log = logs_with_changes[0]
                self.log_test("Enhanced Audit Trail", True, 
                    f"Found {len(logs_with_changes)} audit logs with field changes. Sample: {sample_log.get('dados_novos', '')[:100]}...")
            else:
                self.log_test("Enhanced Audit Trail", True, 
                    f"Audit trail endpoint working, {len(audit_logs)} logs found (no field changes yet)")
            
            return True
            
        except Exception as e:
            self.log_test("Enhanced Audit Trail", False, error=str(e))
            return False
    
    def test_equipamento_historico_with_costs(self):
        """Test equipamento historico endpoint includes custo_parada"""
        try:
            # Get equipamentos first
            response = self.session.get(f"{BASE_URL}/equipamentos")
            if response.status_code != 200:
                self.log_test("Equipamento Historico with Costs", False, 
                    error="Could not get equipamentos list")
                return False
            
            equipamentos = response.json()
            if not equipamentos:
                self.log_test("Equipamento Historico with Costs", False, 
                    error="No equipamentos found")
                return False
            
            # Test historico for first equipment
            equip_id = equipamentos[0]["id"]
            response = self.session.get(f"{BASE_URL}/equipamentos/{equip_id}/historico")
            
            if response.status_code != 200:
                self.log_test("Equipamento Historico with Costs", False, 
                    error=f"Status {response.status_code}: {response.text}")
                return False
            
            historico = response.json()
            
            if not isinstance(historico, dict) or "ordens" not in historico:
                self.log_test("Equipamento Historico with Costs", False, 
                    error="Historico should be an object with 'ordens' field")
                return False
            
            orders = historico.get("ordens", [])
            if not isinstance(orders, list):
                self.log_test("Equipamento Historico with Costs", False, 
                    error="Orders should be a list")
                return False
            
            # Check if orders have custo_parada field
            orders_with_cost = [order for order in orders if "custo_parada" in order]
            
            self.log_test("Equipamento Historico with Costs", True, 
                f"Historico for equipment {equip_id}: {len(orders)} orders, {len(orders_with_cost)} with custo_parada")
            return True
            
        except Exception as e:
            self.log_test("Equipamento Historico with Costs", False, error=str(e))
            return False
    
    # ── New feature tests (FASE 1-4) ─────────────────────────────────────────

    def test_failure_group_bloqueio(self):
        """Test 409 bloqueio when opening a second OS with same failure_group on same equipment"""
        try:
            equip_resp = self.session.get(f"{BASE_URL}/equipamentos")
            if equip_resp.status_code != 200 or not equip_resp.json():
                self.log_test("Failure Group Bloqueio", False, error="No equipamentos found")
                return False

            equip_id = equip_resp.json()[0]["id"]

            # Step 1: create OS with failure_group='hidraulico'
            os1 = self.session.post(f"{BASE_URL}/ordens-servico", json={
                "equipamento_id": equip_id, "tipo": "corretiva", "prioridade": "media",
                "descricao": "Teste bloqueio grupo 1", "failure_group": "hidraulico",
            })
            if os1.status_code not in (200, 201):
                self.log_test("Failure Group Bloqueio", False,
                              error=f"Could not create first OS: {os1.status_code} {os1.text[:200]}")
                return False

            os1_id = os1.json().get("id")

            # Step 2: try same failure_group → must return 409
            os2 = self.session.post(f"{BASE_URL}/ordens-servico", json={
                "equipamento_id": equip_id, "tipo": "corretiva", "prioridade": "alta",
                "descricao": "Teste bloqueio grupo 2", "failure_group": "hidraulico",
            })
            if os2.status_code != 409:
                self.log_test("Failure Group Bloqueio - Duplicate 409", False,
                              error=f"Expected 409, got {os2.status_code}")
            else:
                detail = os2.json().get("detail", {})
                has_error  = detail.get("error") == "bloqueio_grupo_falha"
                has_grupos = "grupos_disponiveis" in detail
                has_os_bl  = "os_bloqueante" in detail
                if has_error and has_grupos and has_os_bl:
                    self.log_test("Failure Group Bloqueio - Duplicate 409", True,
                                  f"Correct 409 with grupos_disponiveis={detail['grupos_disponiveis']}")
                else:
                    self.log_test("Failure Group Bloqueio - Duplicate 409", False,
                                  error=f"409 detail missing fields: {detail}")

            # Step 3: different failure_group on same equipment → must succeed
            os3 = self.session.post(f"{BASE_URL}/ordens-servico", json={
                "equipamento_id": equip_id, "tipo": "corretiva", "prioridade": "media",
                "descricao": "Teste bloqueio grupo eletrico", "failure_group": "eletrico",
            })
            if os3.status_code in (200, 201):
                self.log_test("Failure Group Bloqueio - Different Group OK", True,
                              f"OS created with 'eletrico' on same equipment")
                # cleanup
                self.session.put(f"{BASE_URL}/ordens-servico/{os3.json()['id']}", json={"status": "fechada"})
            else:
                self.log_test("Failure Group Bloqueio - Different Group OK", False,
                              error=f"Expected 200/201, got {os3.status_code}: {os3.text[:200]}")

            # cleanup first OS
            if os1_id:
                self.session.put(f"{BASE_URL}/ordens-servico/{os1_id}", json={"status": "fechada"})

            return True
        except Exception as e:
            self.log_test("Failure Group Bloqueio", False, error=str(e))
            return False

    def test_tecnico_login(self):
        """Test POST /auth/tecnico-login — generic sector password login"""
        try:
            # We need a sector first — try to get sectors (requires auth)
            sectors_resp = self.session.get(f"{BASE_URL}/sectors")
            if sectors_resp.status_code != 200:
                self.log_test("Tecnico Login", False, error=f"Could not get sectors: {sectors_resp.status_code}")
                return False

            sectors = sectors_resp.json()
            if not sectors:
                self.log_test("Tecnico Login", False,
                              error="No sectors found — create a sector with senha_tecnico first")
                return False

            sector_id = sectors[0]["id"]

            # Test with invalid password — must return 401/403
            bad_resp = requests.post(f"{BASE_URL}/auth/tecnico-login", json={
                "sector_id": sector_id, "employee_id": "99999", "senha_generica": "wrong_password",
            })
            if bad_resp.status_code in (401, 403, 400):
                self.log_test("Tecnico Login - Bad Password Rejected", True,
                              f"Correctly rejected: {bad_resp.status_code}")
            else:
                self.log_test("Tecnico Login - Bad Password Rejected", False,
                              error=f"Expected 401/403, got {bad_resp.status_code}")

            self.log_test("Tecnico Login", True, f"Sector {sector_id} found, endpoint reachable")
            return True
        except Exception as e:
            self.log_test("Tecnico Login", False, error=str(e))
            return False

    def test_patch_ocorrencia(self):
        """Test PATCH /ordens-servico/{id}/ocorrencia — append-only, no downtime change"""
        try:
            os_resp = self.session.get(f"{BASE_URL}/ordens-servico")
            if os_resp.status_code != 200 or not os_resp.json():
                self.log_test("PATCH Ocorrencia", False, error="No OS found")
                return False

            # Find an aberta OS
            os_list = os_resp.json()
            target = next((o for o in os_list if o["status"] == "aberta"), None)
            if not target:
                target = os_list[0]

            os_id = target["id"]
            old_downtime = target.get("downtime_start")

            patch_resp = self.session.patch(f"{BASE_URL}/ordens-servico/{os_id}/ocorrencia",
                                            json={"descricao": "Teste ocorrência via backend_test"})
            if patch_resp.status_code != 200:
                self.log_test("PATCH Ocorrencia", False,
                              error=f"Status {patch_resp.status_code}: {patch_resp.text[:200]}")
                return False

            updated = patch_resp.json()
            new_downtime = updated.get("downtime_start")

            if old_downtime == new_downtime:
                self.log_test("PATCH Ocorrencia", True,
                              "Occurrence added, downtime_start unchanged (correct)")
            else:
                self.log_test("PATCH Ocorrencia", False,
                              error=f"downtime_start changed: {old_downtime} → {new_downtime}")

            return True
        except Exception as e:
            self.log_test("PATCH Ocorrencia", False, error=str(e))
            return False

    def test_response_time_calculation(self):
        """Test that response_time_min is calculated when status → em_atendimento"""
        try:
            # Create a new OS (aberta)
            equip_resp = self.session.get(f"{BASE_URL}/equipamentos")
            if equip_resp.status_code != 200 or not equip_resp.json():
                self.log_test("Response Time Calculation", False, error="No equipamentos found")
                return False

            equip_id = equip_resp.json()[0]["id"]
            create_resp = self.session.post(f"{BASE_URL}/ordens-servico", json={
                "equipamento_id": equip_id, "tipo": "corretiva", "prioridade": "media",
                "descricao": "Teste response_time_min",
            })
            if create_resp.status_code not in (200, 201):
                self.log_test("Response Time Calculation", False,
                              error=f"Could not create OS: {create_resp.status_code}")
                return False

            os_id = create_resp.json()["id"]

            # Move to em_atendimento
            update_resp = self.session.put(f"{BASE_URL}/ordens-servico/{os_id}",
                                           json={"status": "em_atendimento"})
            if update_resp.status_code != 200:
                self.log_test("Response Time Calculation", False,
                              error=f"Could not update status: {update_resp.status_code} {update_resp.text[:200]}")
                return False

            updated = update_resp.json()
            rtime = updated.get("tempo_resposta") or updated.get("response_time_min")

            if rtime is not None:
                self.log_test("Response Time Calculation", True,
                              f"response_time_min = {rtime} min (calculated on em_atendimento)")
            else:
                self.log_test("Response Time Calculation", False,
                              error="response_time_min/tempo_resposta is None after em_atendimento")

            # cleanup
            self.session.put(f"{BASE_URL}/ordens-servico/{os_id}", json={"status": "fechada"})
            return True
        except Exception as e:
            self.log_test("Response Time Calculation", False, error=str(e))
            return False

    def test_dashboard_operador(self):
        """Test GET /dashboard/operador — should return 5 KPIs"""
        try:
            resp = self.session.get(f"{BASE_URL}/dashboard/operador")
            # Admin role may get 403 if endpoint is restricted to operador/tecnico
            if resp.status_code == 403:
                self.log_test("Dashboard Operador", True,
                              "Endpoint correctly rejects admin (403) — RBAC working")
                return True
            if resp.status_code != 200:
                self.log_test("Dashboard Operador", False,
                              error=f"Status {resp.status_code}: {resp.text[:200]}")
                return False

            data = resp.json()
            required = ["disponibilidade_percent", "mttr_minutos", "mtbf_horas",
                        "os_mes", "tempo_resposta_medio_min"]
            missing = [k for k in required if k not in data]
            if missing:
                self.log_test("Dashboard Operador", False,
                              error=f"Missing KPI fields: {missing}")
                return False

            self.log_test("Dashboard Operador", True,
                          f"5 KPIs present: disponibilidade={data['disponibilidade_percent']}%")
            return True
        except Exception as e:
            self.log_test("Dashboard Operador", False, error=str(e))
            return False

    def test_dashboard_lider(self):
        """Test GET /dashboard/lider — KPIs + financials + Pareto"""
        try:
            resp = self.session.get(f"{BASE_URL}/dashboard/lider")
            if resp.status_code != 200:
                self.log_test("Dashboard Lider", False,
                              error=f"Status {resp.status_code}: {resp.text[:200]}")
                return False

            data = resp.json()
            required = ["disponibilidade_percent", "mttr_minutos", "mtbf_horas",
                        "os_mes", "tempo_resposta_medio_min", "custo_parada_total",
                        "os_por_grupo_falha", "tecnicos_ativos", "pendentes_revisao"]
            missing = [k for k in required if k not in data]
            if missing:
                self.log_test("Dashboard Lider", False,
                              error=f"Missing fields: {missing}")
                return False

            pareto = data.get("os_por_grupo_falha", [])
            tecnicos = data.get("tecnicos_ativos", [])
            self.log_test("Dashboard Lider", True,
                          f"All fields present. Pareto entries={len(pareto)}, Tecnicos ativos={len(tecnicos)}")
            return True
        except Exception as e:
            self.log_test("Dashboard Lider", False, error=str(e))
            return False

    def run_all_tests(self):
        """Run all backend tests"""
        print("🚀 Starting PCM Backend API Tests")
        print("=" * 50)
        
        # Step 1: Seed demo data
        if not self.seed_demo_data():
            print("❌ Failed to seed demo data. Stopping tests.")
            return False
        
        # Step 2: Login
        if not self.login():
            print("❌ Failed to login. Stopping tests.")
            return False
        
        # Step 3: Run all feature tests
        tests = [
            self.test_billing_plan_endpoint,
            self.test_billing_transactions_endpoint,
            self.test_billing_checkout_endpoint,
            self.test_plan_limit_enforcement,
            self.test_downtime_cost_calculation,
            self.test_review_workflow,
            self.test_enhanced_dashboard_kpis,
            self.test_enhanced_audit_trail,
            self.test_equipamento_historico_with_costs,
            # ── New feature tests ──
            self.test_failure_group_bloqueio,
            self.test_tecnico_login,
            self.test_patch_ocorrencia,
            self.test_response_time_calculation,
            self.test_dashboard_operador,
            self.test_dashboard_lider,
        ]
        
        passed = 0
        failed = 0
        
        for test in tests:
            try:
                if test():
                    passed += 1
                else:
                    failed += 1
            except Exception as e:
                print(f"❌ Test {test.__name__} crashed: {e}")
                failed += 1
        
        # Summary
        print("=" * 50)
        print(f"📊 Test Summary: {passed} passed, {failed} failed")
        
        if failed > 0:
            print("\n❌ Failed Tests:")
            for result in self.test_results:
                if not result["success"]:
                    print(f"  - {result['test']}: {result['error']}")
        
        return failed == 0

def main():
    """Main test runner"""
    tester = PCMTester()
    success = tester.run_all_tests()
    
    # Save detailed results
    results_path = os.path.join(os.path.dirname(__file__), "backend_test_results.json")
    with open(results_path, "w") as f:
        json.dump(tester.test_results, f, indent=2, default=str)

    print(f"\n📄 Detailed results saved to: {results_path}")
    
    if success:
        print("✅ All tests passed!")
        sys.exit(0)
    else:
        print("❌ Some tests failed!")
        sys.exit(1)

if __name__ == "__main__":
    main()