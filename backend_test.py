#!/usr/bin/env python3
"""
PCM Backend API Testing Suite
Tests all backend endpoints for the Industrial Maintenance Management System
"""

import requests
import sys
import json
from datetime import datetime
from typing import Dict, Any, Optional

class PCMAPITester:
    def __init__(self, base_url: str = "https://saas-multi-tenant-2.preview.emergentagent.com"):
        self.base_url = base_url
        self.token = None
        self.user_data = None
        self.tests_run = 0
        self.tests_passed = 0
        self.failed_tests = []
        
        # Test data storage
        self.created_equipamento_id = None
        self.created_os_id = None
        self.created_plano_id = None

    def log_result(self, test_name: str, success: bool, details: str = ""):
        """Log test result"""
        self.tests_run += 1
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} - {test_name}")
        if details:
            print(f"    {details}")
        if success:
            self.tests_passed += 1
        else:
            self.failed_tests.append(f"{test_name}: {details}")
        print()

    def make_request(self, method: str, endpoint: str, data: Optional[Dict] = None, 
                    expected_status: int = 200, auth_required: bool = True) -> tuple[bool, Dict]:
        """Make HTTP request with error handling"""
        url = f"{self.base_url}/api/{endpoint}"
        headers = {'Content-Type': 'application/json'}
        
        if auth_required and self.token:
            headers['Authorization'] = f'Bearer {self.token}'
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, timeout=30)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=headers, timeout=30)
            elif method == 'PUT':
                response = requests.put(url, json=data, headers=headers, timeout=30)
            elif method == 'DELETE':
                response = requests.delete(url, headers=headers, timeout=30)
            else:
                return False, {"error": f"Unsupported method: {method}"}

            success = response.status_code == expected_status
            try:
                response_data = response.json()
            except:
                response_data = {"status_code": response.status_code, "text": response.text[:200]}
            
            if not success:
                response_data["status_code"] = response.status_code
                
            return success, response_data
            
        except requests.exceptions.RequestException as e:
            return False, {"error": str(e)}

    def test_login(self) -> bool:
        """Test login with demo admin credentials"""
        print("🔐 Testing Authentication...")
        
        success, response = self.make_request(
            'POST', 'auth/login',
            data={"email": "admin@demo.pcm", "password": "admin123"},
            auth_required=False
        )
        
        if success and 'access_token' in response:
            self.token = response['access_token']
            self.user_data = response
            self.log_result("Admin Login", True, f"Logged in as {response.get('nome', 'Admin')}")
            return True
        else:
            self.log_result("Admin Login", False, f"Login failed: {response}")
            return False

    def test_auth_me(self) -> bool:
        """Test getting current user info"""
        success, response = self.make_request('GET', 'auth/me')
        
        if success and response.get('role') == 'admin':
            self.log_result("Get Current User", True, f"User: {response.get('nome')} ({response.get('role')})")
            return True
        else:
            self.log_result("Get Current User", False, f"Failed to get user info: {response}")
            return False

    def test_dashboard_kpis(self) -> bool:
        """Test dashboard KPIs endpoint"""
        print("📊 Testing Dashboard...")
        
        success, response = self.make_request('GET', 'dashboard/kpis')
        
        if success:
            kpis = ['total_os_mes', 'os_abertas', 'mttr', 'mtbf', 'disponibilidade']
            missing_kpis = [kpi for kpi in kpis if kpi not in response]
            
            if not missing_kpis:
                self.log_result("Dashboard KPIs", True, 
                    f"MTTR: {response.get('mttr', 0):.1f}h, MTBF: {response.get('mtbf', 0):.1f}h, "
                    f"Disponibilidade: {response.get('disponibilidade', 0):.1f}%")
                return True
            else:
                self.log_result("Dashboard KPIs", False, f"Missing KPIs: {missing_kpis}")
                return False
        else:
            self.log_result("Dashboard KPIs", False, f"Request failed: {response}")
            return False

    def test_dashboard_backlog(self) -> bool:
        """Test dashboard backlog endpoint"""
        success, response = self.make_request('GET', 'dashboard/backlog')
        
        if success:
            backlog_fields = ['abertas', 'em_atendimento', 'aguardando_revisao', 'atrasadas']
            missing_fields = [field for field in backlog_fields if field not in response]
            
            if not missing_fields:
                self.log_result("Dashboard Backlog", True, 
                    f"Abertas: {response.get('abertas', 0)}, Em atendimento: {response.get('em_atendimento', 0)}")
                return True
            else:
                self.log_result("Dashboard Backlog", False, f"Missing fields: {missing_fields}")
                return False
        else:
            self.log_result("Dashboard Backlog", False, f"Request failed: {response}")
            return False

    def test_equipamentos(self) -> bool:
        """Test equipment endpoints"""
        print("🔧 Testing Equipment Management...")
        
        # List equipamentos
        success, response = self.make_request('GET', 'equipamentos')
        if not success:
            self.log_result("List Equipamentos", False, f"Failed to list: {response}")
            return False
        
        equipamentos = response if isinstance(response, list) else []
        self.log_result("List Equipamentos", True, f"Found {len(equipamentos)} equipamentos")
        
        # Create new equipamento
        new_equipamento = {
            "codigo": f"TEST-{datetime.now().strftime('%H%M%S')}",
            "nome": "Equipamento Teste",
            "descricao": "Equipamento criado para teste",
            "localizacao": "Setor Teste",
            "valor_hora": 100.0,
            "criticidade": 3
        }
        
        success, response = self.make_request('POST', 'equipamentos', data=new_equipamento, expected_status=200)
        if success and 'id' in response:
            self.created_equipamento_id = response['id']
            self.log_result("Create Equipamento", True, f"Created equipamento {response['codigo']}")
            return True
        else:
            self.log_result("Create Equipamento", False, f"Failed to create: {response}")
            return False

    def test_ordens_servico(self) -> bool:
        """Test service orders endpoints"""
        print("📋 Testing Service Orders...")
        
        # List ordens de serviço
        success, response = self.make_request('GET', 'ordens-servico')
        if not success:
            self.log_result("List Ordens Serviço", False, f"Failed to list: {response}")
            return False
        
        ordens = response if isinstance(response, list) else []
        self.log_result("List Ordens Serviço", True, f"Found {len(ordens)} ordens")
        
        # Create new OS if we have an equipamento
        if self.created_equipamento_id:
            new_os = {
                "equipamento_id": self.created_equipamento_id,
                "tipo": "corretiva",
                "prioridade": "media",
                "descricao": "Ordem de serviço de teste",
                "falha_tipo": "Mecânica",
                "falha_modo": "Teste",
                "falha_causa": "Teste automatizado"
            }
            
            success, response = self.make_request('POST', 'ordens-servico', data=new_os, expected_status=200)
            if success and 'id' in response:
                self.created_os_id = response['id']
                self.log_result("Create Ordem Serviço", True, f"Created OS #{response.get('numero', 'N/A')}")
                return True
            else:
                self.log_result("Create Ordem Serviço", False, f"Failed to create: {response}")
                return False
        else:
            self.log_result("Create Ordem Serviço", False, "No equipamento available for testing")
            return False

    def test_planos_preventivos(self) -> bool:
        """Test preventive plans endpoints"""
        print("🗓️ Testing Preventive Plans...")
        
        # List planos preventivos
        success, response = self.make_request('GET', 'planos-preventivos')
        if not success:
            self.log_result("List Planos Preventivos", False, f"Failed to list: {response}")
            return False
        
        planos = response if isinstance(response, list) else []
        self.log_result("List Planos Preventivos", True, f"Found {len(planos)} planos")
        
        # Create new plano if we have an equipamento
        if self.created_equipamento_id:
            new_plano = {
                "equipamento_id": self.created_equipamento_id,
                "nome": "Plano de Teste",
                "descricao": "Plano preventivo de teste",
                "frequencia_dias": 30
            }
            
            success, response = self.make_request('POST', 'planos-preventivos', data=new_plano, expected_status=200)
            if success and 'id' in response:
                self.created_plano_id = response['id']
                self.log_result("Create Plano Preventivo", True, f"Created plano {response['nome']}")
                return True
            else:
                self.log_result("Create Plano Preventivo", False, f"Failed to create: {response}")
                return False
        else:
            self.log_result("Create Plano Preventivo", False, "No equipamento available for testing")
            return False

    def test_users(self) -> bool:
        """Test users endpoints (admin only)"""
        print("👥 Testing User Management...")
        
        success, response = self.make_request('GET', 'users')
        if success:
            users = response if isinstance(response, list) else []
            admin_users = [u for u in users if u.get('role') == 'admin']
            self.log_result("List Users", True, f"Found {len(users)} users, {len(admin_users)} admins")
            return True
        else:
            self.log_result("List Users", False, f"Failed to list users: {response}")
            return False

    def test_auditoria(self) -> bool:
        """Test audit log endpoints (admin only)"""
        print("📝 Testing Audit Logs...")
        
        success, response = self.make_request('GET', 'auditoria')
        if success:
            logs = response if isinstance(response, list) else []
            self.log_result("List Auditoria", True, f"Found {len(logs)} audit logs")
            return True
        else:
            self.log_result("List Auditoria", False, f"Failed to list audit logs: {response}")
            return False

    def test_grupos_subgrupos(self) -> bool:
        """Test groups and subgroups endpoints"""
        print("🏷️ Testing Groups and Subgroups...")
        
        # Test grupos
        success, response = self.make_request('GET', 'grupos')
        if success:
            grupos = response if isinstance(response, list) else []
            self.log_result("List Grupos", True, f"Found {len(grupos)} grupos")
        else:
            self.log_result("List Grupos", False, f"Failed to list grupos: {response}")
            return False
        
        # Test subgrupos
        success, response = self.make_request('GET', 'subgrupos')
        if success:
            subgrupos = response if isinstance(response, list) else []
            self.log_result("List Subgrupos", True, f"Found {len(subgrupos)} subgrupos")
            return True
        else:
            self.log_result("List Subgrupos", False, f"Failed to list subgrupos: {response}")
            return False

    def test_seed_demo(self) -> bool:
        """Test seed demo data endpoint"""
        print("🌱 Testing Demo Data Seeding...")
        
        success, response = self.make_request('POST', 'seed-demo', auth_required=False)
        if success or (response.get('message', '').find('já existem') != -1):
            self.log_result("Seed Demo Data", True, "Demo data available")
            return True
        else:
            self.log_result("Seed Demo Data", False, f"Failed to seed: {response}")
            return False

    def test_logout(self) -> bool:
        """Test logout endpoint"""
        success, response = self.make_request('POST', 'auth/logout')
        if success:
            self.log_result("Logout", True, "Successfully logged out")
            return True
        else:
            self.log_result("Logout", False, f"Logout failed: {response}")
            return False

    def run_all_tests(self) -> bool:
        """Run all backend tests"""
        print("🚀 Starting PCM Backend API Tests")
        print("=" * 50)
        
        # Authentication tests
        if not self.test_login():
            print("❌ Authentication failed - stopping tests")
            return False
        
        self.test_auth_me()
        
        # Core functionality tests
        self.test_seed_demo()
        self.test_dashboard_kpis()
        self.test_dashboard_backlog()
        self.test_equipamentos()
        self.test_ordens_servico()
        self.test_planos_preventivos()
        self.test_grupos_subgrupos()
        
        # Admin-only tests
        self.test_users()
        self.test_auditoria()
        
        # Cleanup
        self.test_logout()
        
        # Summary
        print("=" * 50)
        print(f"📊 Test Results: {self.tests_passed}/{self.tests_run} passed")
        
        if self.failed_tests:
            print("\n❌ Failed Tests:")
            for failure in self.failed_tests:
                print(f"  - {failure}")
        
        success_rate = (self.tests_passed / self.tests_run * 100) if self.tests_run > 0 else 0
        print(f"✅ Success Rate: {success_rate:.1f}%")
        
        return success_rate >= 80  # Consider 80%+ success rate as passing

def main():
    """Main test execution"""
    tester = PCMAPITester()
    success = tester.run_all_tests()
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())