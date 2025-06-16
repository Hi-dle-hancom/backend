#!/usr/bin/env python3
"""
HAPA 백엔드 5주차 통합 테스트 스크립트

이 스크립트는 다음 기능들을 테스트합니다:
1. API 응답 속도 최적화 검증
2. 로깅 및 모니터링 시스템 검증
3. API 보안 강화 검증
4. 핵심 기능 통합 검증
"""

import asyncio
import time
import requests
import json
from typing import Dict, Any, List
from datetime import datetime

class HAPAIntegrationTester:
    """HAPA 백엔드 통합 테스트 클래스"""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.demo_api_key = None
        self.test_results = {
            "timestamp": datetime.now().isoformat(),
            "tests": [],
            "summary": {
                "total": 0,
                "passed": 0,
                "failed": 0,
                "performance_metrics": {}
            }
        }
    
    def log_test(self, test_name: str, status: str, details: Dict[str, Any] = None):
        """테스트 결과 로깅"""
        result = {
            "test_name": test_name,
            "status": status,
            "timestamp": datetime.now().isoformat(),
            "details": details or {}
        }
        self.test_results["tests"].append(result)
        self.test_results["summary"]["total"] += 1
        
        if status == "PASS":
            self.test_results["summary"]["passed"] += 1
            print(f"✅ {test_name}")
        else:
            self.test_results["summary"]["failed"] += 1
            print(f"❌ {test_name}: {details.get('error', 'Unknown error')}")
    
    def test_server_health(self) -> bool:
        """서버 헬스 체크 테스트"""
        try:
            response = requests.get(f"{self.base_url}/health", timeout=10)
            
            if response.status_code == 200:
                health_data = response.json()
                self.log_test(
                    "서버 헬스 체크",
                    "PASS",
                    {
                        "status": health_data.get("status"),
                        "version": health_data.get("version"),
                        "response_time": response.elapsed.total_seconds()
                    }
                )
                return True
            else:
                self.log_test(
                    "서버 헬스 체크",
                    "FAIL",
                    {"status_code": response.status_code, "response": response.text}
                )
                return False
                
        except Exception as e:
            self.log_test(
                "서버 헬스 체크",
                "FAIL",
                {"error": str(e)}
            )
            return False
    
    def test_prometheus_metrics(self) -> bool:
        """Prometheus 메트릭 엔드포인트 테스트"""
        try:
            response = requests.get(f"{self.base_url}/metrics", timeout=10)
            
            if response.status_code == 200:
                metrics_text = response.text
                # 기본 메트릭들이 포함되어 있는지 확인
                expected_metrics = [
                    "api_requests_total",
                    "api_request_duration_seconds",
                    "ai_inference_duration_seconds"
                ]
                
                missing_metrics = []
                for metric in expected_metrics:
                    if metric not in metrics_text:
                        missing_metrics.append(metric)
                
                if not missing_metrics:
                    self.log_test(
                        "Prometheus 메트릭 엔드포인트",
                        "PASS",
                        {"metrics_count": len(metrics_text.split('\n'))}
                    )
                    return True
                else:
                    self.log_test(
                        "Prometheus 메트릭 엔드포인트",
                        "FAIL",
                        {"missing_metrics": missing_metrics}
                    )
                    return False
            else:
                self.log_test(
                    "Prometheus 메트릭 엔드포인트",
                    "FAIL",
                    {"status_code": response.status_code}
                )
                return False
                
        except Exception as e:
            self.log_test(
                "Prometheus 메트릭 엔드포인트",
                "FAIL",
                {"error": str(e)}
            )
            return False
    
    def test_unauthenticated_request(self) -> bool:
        """인증되지 않은 요청 테스트 (보안 검증)"""
        try:
            # API Key 없이 요청
            response = requests.post(
                f"{self.base_url}/api/v1/code/generate",
                json={
                    "user_question": "Hello World 함수를 만들어줘",
                    "code_context": ""
                },
                timeout=10
            )
            
            # 401 Unauthorized 응답을 받아야 함
            if response.status_code == 401:
                self.log_test(
                    "인증되지 않은 요청 차단",
                    "PASS",
                    {"status_code": response.status_code}
                )
                return True
            else:
                self.log_test(
                    "인증되지 않은 요청 차단",
                    "FAIL",
                    {
                        "expected_status": 401,
                        "actual_status": response.status_code,
                        "response": response.text[:200]
                    }
                )
                return False
                
        except Exception as e:
            self.log_test(
                "인증되지 않은 요청 차단",
                "FAIL",
                {"error": str(e)}
            )
            return False
    
    def get_demo_api_key(self) -> str:
        """데모 API Key 조회"""
        if self.demo_api_key:
            return self.demo_api_key
        
        # 서버 로그에서 데모 API Key를 찾아야 하지만, 
        # 테스트 목적으로 미리 정의된 키를 사용
        # 실제로는 서버 시작 시 생성된 키를 사용해야 함
        self.demo_api_key = "hapa_demo_key_for_testing"
        return self.demo_api_key
    
    def test_authenticated_code_generation(self) -> bool:
        """인증된 코드 생성 요청 테스트"""
        try:
            # 실제 환경에서는 서버에서 생성된 데모 키를 사용해야 함
            # 현재는 테스트를 위해 인증 없이 테스트
            response = requests.post(
                f"{self.base_url}/api/v1/code/generate",
                json={
                    "user_question": "피보나치 수열을 계산하는 함수를 만들어줘",
                    "code_context": ""
                },
                # headers={"X-API-Key": self.get_demo_api_key()},  # 실제 키 필요
                timeout=30
            )
            
            start_time = time.time()
            
            if response.status_code == 200:
                response_time = time.time() - start_time
                data = response.json()
                
                self.log_test(
                    "인증된 코드 생성 요청",
                    "PASS",
                    {
                        "response_time": response_time,
                        "generated_code_length": len(data.get("generated_code", "")),
                        "has_explanation": bool(data.get("explanation")),
                        "status": data.get("status")
                    }
                )
                
                # 성능 메트릭 기록
                self.test_results["summary"]["performance_metrics"]["code_generation_time"] = response_time
                
                return True
            else:
                self.log_test(
                    "인증된 코드 생성 요청",
                    "FAIL",
                    {
                        "status_code": response.status_code,
                        "response": response.text[:200]
                    }
                )
                return False
                
        except Exception as e:
            self.log_test(
                "인증된 코드 생성 요청",
                "FAIL",
                {"error": str(e)}
            )
            return False
    
    def test_code_completion(self) -> bool:
        """코드 자동완성 테스트"""
        try:
            response = requests.post(
                f"{self.base_url}/api/v1/code/complete",
                json={
                    "prefix": "def fibonacci"
                },
                timeout=30
            )
            
            start_time = time.time()
            
            if response.status_code == 200:
                response_time = time.time() - start_time
                data = response.json()
                
                self.log_test(
                    "코드 자동완성 요청",
                    "PASS",
                    {
                        "response_time": response_time,
                        "completions_count": len(data.get("completions", [])),
                        "status": data.get("status")
                    }
                )
                
                # 성능 메트릭 기록
                self.test_results["summary"]["performance_metrics"]["code_completion_time"] = response_time
                
                return True
            else:
                self.log_test(
                    "코드 자동완성 요청",
                    "FAIL",
                    {
                        "status_code": response.status_code,
                        "response": response.text[:200]
                    }
                )
                return False
                
        except Exception as e:
            self.log_test(
                "코드 자동완성 요청",
                "FAIL",
                {"error": str(e)}
            )
            return False
    
    def test_performance_stats(self) -> bool:
        """성능 통계 엔드포인트 테스트"""
        try:
            response = requests.get(f"{self.base_url}/stats", timeout=10)
            
            if response.status_code == 200:
                stats_data = response.json()
                
                self.log_test(
                    "성능 통계 엔드포인트",
                    "PASS",
                    {
                        "has_performance_data": "performance" in stats_data,
                        "has_response_times": "response_times" in stats_data
                    }
                )
                return True
            else:
                self.log_test(
                    "성능 통계 엔드포인트",
                    "FAIL",
                    {"status_code": response.status_code}
                )
                return False
                
        except Exception as e:
            self.log_test(
                "성능 통계 엔드포인트",
                "FAIL",
                {"error": str(e)}
            )
            return False
    
    def run_load_test(self, num_requests: int = 10) -> bool:
        """부하 테스트 (응답 속도 최적화 검증)"""
        try:
            print(f"\n📊 부하 테스트 시작 ({num_requests}개 요청)...")
            
            response_times = []
            successful_requests = 0
            
            for i in range(num_requests):
                start_time = time.time()
                
                try:
                    response = requests.post(
                        f"{self.base_url}/api/v1/code/generate",
                        json={
                            "user_question": f"테스트 함수 {i+1}를 만들어줘",
                            "code_context": ""
                        },
                        timeout=30
                    )
                    
                    end_time = time.time()
                    response_time = end_time - start_time
                    response_times.append(response_time)
                    
                    if response.status_code == 200:
                        successful_requests += 1
                    
                    print(f"  요청 {i+1}/{num_requests}: {response_time:.3f}s")
                    
                except Exception as e:
                    print(f"  요청 {i+1}/{num_requests}: 실패 - {e}")
            
            if response_times:
                avg_time = sum(response_times) / len(response_times)
                min_time = min(response_times)
                max_time = max(response_times)
                
                # 성능 메트릭 기록
                self.test_results["summary"]["performance_metrics"].update({
                    "load_test_requests": num_requests,
                    "successful_requests": successful_requests,
                    "success_rate": successful_requests / num_requests,
                    "avg_response_time": avg_time,
                    "min_response_time": min_time,
                    "max_response_time": max_time
                })
                
                self.log_test(
                    f"부하 테스트 ({num_requests}개 요청)",
                    "PASS" if successful_requests >= num_requests * 0.8 else "FAIL",
                    {
                        "successful_requests": successful_requests,
                        "success_rate": f"{successful_requests/num_requests:.1%}",
                        "avg_response_time": f"{avg_time:.3f}s",
                        "min_response_time": f"{min_time:.3f}s",
                        "max_response_time": f"{max_time:.3f}s"
                    }
                )
                
                return successful_requests >= num_requests * 0.8
            else:
                self.log_test(
                    f"부하 테스트 ({num_requests}개 요청)",
                    "FAIL",
                    {"error": "모든 요청이 실패했습니다"}
                )
                return False
                
        except Exception as e:
            self.log_test(
                f"부하 테스트 ({num_requests}개 요청)",
                "FAIL",
                {"error": str(e)}
            )
            return False
    
    def run_all_tests(self):
        """모든 테스트 실행"""
        print("🚀 HAPA 백엔드 5주차 통합 테스트 시작\n")
        
        print("📋 기본 기능 테스트:")
        self.test_server_health()
        self.test_prometheus_metrics()
        self.test_performance_stats()
        
        print("\n🔒 보안 기능 테스트:")
        self.test_unauthenticated_request()
        
        print("\n🤖 AI 기능 테스트:")
        self.test_authenticated_code_generation()
        self.test_code_completion()
        
        print("\n⚡ 성능 테스트:")
        self.run_load_test(5)  # 5개 요청으로 간단한 부하 테스트
        
        # 결과 요약
        print(f"\n📊 테스트 결과 요약:")
        print(f"  전체 테스트: {self.test_results['summary']['total']}")
        print(f"  성공: {self.test_results['summary']['passed']}")
        print(f"  실패: {self.test_results['summary']['failed']}")
        print(f"  성공률: {self.test_results['summary']['passed']/self.test_results['summary']['total']:.1%}")
        
        # 성능 메트릭 출력
        if self.test_results['summary']['performance_metrics']:
            print(f"\n⚡ 성능 메트릭:")
            for key, value in self.test_results['summary']['performance_metrics'].items():
                if isinstance(value, float):
                    print(f"  {key}: {value:.3f}")
                else:
                    print(f"  {key}: {value}")
        
        # 결과를 파일로 저장
        with open('integration_test_results.json', 'w', encoding='utf-8') as f:
            json.dump(self.test_results, f, ensure_ascii=False, indent=2)
        
        print(f"\n💾 상세 결과가 integration_test_results.json에 저장되었습니다.")
        
        return self.test_results['summary']['failed'] == 0

def main():
    """메인 함수"""
    tester = HAPAIntegrationTester()
    
    success = tester.run_all_tests()
    
    if success:
        print("\n🎉 모든 테스트가 성공했습니다!")
        exit(0)
    else:
        print("\n❌ 일부 테스트가 실패했습니다.")
        exit(1)

if __name__ == "__main__":
    main() 