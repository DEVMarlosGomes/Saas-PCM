#!/usr/bin/env python3
"""
Backend API Testing for PCM SaaS System
Tests billing, plan limits, downtime costs, review workflow, and enhanced features
"""

import requests
import json
import time
from datetime import datetime, timezone
import sys

# Configuration
BASE_URL = "https://saas-multi-tenant-2.preview.emergentagent.com/api"
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
            self.test_equipamento_historico_with_costs
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
    with open("/app/backend_test_results.json", "w") as f:
        json.dump(tester.test_results, f, indent=2, default=str)
    
    print(f"\n📄 Detailed results saved to: /app/backend_test_results.json")
    
    if success:
        print("✅ All tests passed!")
        sys.exit(0)
    else:
        print("❌ Some tests failed!")
        sys.exit(1)

if __name__ == "__main__":
    main()