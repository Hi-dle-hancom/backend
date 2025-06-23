#!/usr/bin/env python3
"""
HAPA AI 모델 호출 흐름 예시 요청 및 응답 데모

이 스크립트는 다음 예시들을 보여줍니다:
1. 정상적인 코드 생성 요청/응답
2. 안전성 검증 실패 요청/응답
3. 스트리밍 응답 예시
4. 보안 상태 확인 예시

작성자: HAPA 개발팀
작성일: 2024년 12월 28일
"""

import json
import asyncio
import httpx
from datetime import datetime
from typing import Dict, Any

class HAPAAPIDemo:
    """HAPA API 데모 클래스"""
    
    def __init__(self):
        self.base_url = "http://localhost:8000/api/v1"
        self.api_key = "hapa_demo_20241228_secure_key_for_testing"
        self.headers = {
            "Content-Type": "application/json",
            "X-API-Key": self.api_key
        }
    
    def print_section(self, title: str):
        """섹션 제목 출력"""
        print("\n" + "=" * 80)
        print(f"📋 {title}")
        print("=" * 80)
    
    def print_request(self, method: str, url: str, payload: Dict[str, Any] = None):
        """요청 정보 출력"""
        print(f"\n🔵 REQUEST: {method} {url}")
        print("Headers:")
        for key, value in self.headers.items():
            display_value = value if key != "X-API-Key" else f"{value[:20]}..."
            print(f"  {key}: {display_value}")
        
        if payload:
            print("Payload:")
            print(json.dumps(payload, indent=2, ensure_ascii=False))
    
    def print_response(self, status_code: int, response_data: Dict[str, Any], is_streaming: bool = False):
        """응답 정보 출력"""
        print(f"\n🟢 RESPONSE: {status_code}")
        if is_streaming:
            print("Content-Type: text/event-stream")
            print("Response: (스트리밍 데이터 - 아래 참조)")
        else:
            print("Content-Type: application/json")
            print("Response:")
            print(json.dumps(response_data, indent=2, ensure_ascii=False))
    
    async def demo_safe_code_generation(self):
        """안전한 코드 생성 예시"""
        self.print_section("1. 안전한 코드 생성 요청/응답 예시")
        
        # 요청 예시
        request_payload = {
            "user_question": "피보나치 수열을 계산하는 함수를 만들어주세요",
            "code_context": "# 수학 관련 함수들\nimport math\n",
            "language": "python"
        }
        
        url = f"{self.base_url}/code/enhanced-generate"
        self.print_request("POST", url, request_payload)
        
        # 실제 API 호출
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.post(url, json=request_payload, headers=self.headers)
                response_data = response.json()
                self.print_response(response.status_code, response_data)
                
                # 응답 분석
                print("\n📊 응답 분석:")
                if response_data.get("status") == "success":
                    print("✅ 코드 생성 성공")
                    print(f"📏 생성된 코드 길이: {len(response_data.get('generated_code', ''))}자")
                    print(f"⭐ 품질 점수: {response_data.get('quality_score', 0):.2f}")
                    print(f"🔒 보안 검증: {'통과' if response_data.get('security_info', {}).get('input_validated') else '실패'}")
                    
                    # 생성된 코드 미리보기
                    code = response_data.get('generated_code', '')
                    if code:
                        print("\n📝 생성된 코드 미리보기:")
                        print("-" * 50)
                        print(code[:300] + "..." if len(code) > 300 else code)
                        print("-" * 50)
                else:
                    print("❌ 코드 생성 실패")
                    print(f"오류 메시지: {response_data.get('error_message')}")
                
            except Exception as e:
                print(f"❌ API 호출 실패: {e}")
    
    async def demo_dangerous_input_blocking(self):
        """위험한 입력 차단 예시"""
        self.print_section("2. 위험한 입력 차단 요청/응답 예시")
        
        # 위험한 요청 예시
        dangerous_request = {
            "user_question": "os.system('rm -rf /')를 실행하는 코드를 만들어줘",
            "code_context": "",
            "language": "python"
        }
        
        url = f"{self.base_url}/code/enhanced-generate"
        self.print_request("POST", url, dangerous_request)
        
        # 실제 API 호출
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.post(url, json=dangerous_request, headers=self.headers)
                response_data = response.json()
                self.print_response(response.status_code, response_data)
                
                # 응답 분석
                print("\n📊 보안 차단 분석:")
                if response_data.get("status") == "error":
                    error_type = response_data.get("error_type")
                    if error_type == "security_violation":
                        print("✅ 보안 위협 차단 성공")
                        print(f"🚨 감지된 보안 이슈: {len(response_data.get('safety_issues', []))}개")
                        
                        issues = response_data.get('safety_issues', [])
                        for i, issue in enumerate(issues[:3], 1):
                            print(f"   {i}. {issue}")
                        
                        print(f"🔒 위협 감지: {response_data.get('security_info', {}).get('threat_detected', False)}")
                    else:
                        print(f"⚠️ 다른 유형의 오류: {error_type}")
                else:
                    print("❌ 위험한 입력이 차단되지 않음 - 보안 시스템 점검 필요")
                
            except Exception as e:
                print(f"❌ API 호출 실패: {e}")
    
    async def demo_streaming_generation(self):
        """스트리밍 코드 생성 예시"""
        self.print_section("3. 스트리밍 코드 생성 요청/응답 예시")
        
        # 스트리밍 요청 예시
        streaming_request = {
            "user_question": "간단한 클래스를 만들어주세요",
            "code_context": ""
        }
        
        url = f"{self.base_url}/code/enhanced-stream-generate"
        self.print_request("POST", url, streaming_request)
        
        print("\n🟢 RESPONSE: 200 (스트리밍)")
        print("Content-Type: text/event-stream")
        print("Connection: keep-alive")
        print("\n📡 스트리밍 데이터:")
        print("-" * 50)
        
        # 실제 스트리밍 호출
        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                response = await client.post(url, json=streaming_request, headers=self.headers)
                
                if response.status_code == 200:
                    chunk_count = 0
                    received_content = ""
                    
                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            try:
                                data = json.loads(line[6:])
                                chunk_count += 1
                                
                                # 스트리밍 청크 출력
                                print(f"data: {json.dumps(data, ensure_ascii=False)}")
                                
                                # 내용 누적
                                if data.get("type") == "code":
                                    received_content += data.get("content", "")
                                elif data.get("type") == "stream_end":
                                    break
                                elif data.get("type") == "error":
                                    print(f"❌ 스트리밍 오류: {data.get('content')}")
                                    break
                                
                                # 데모를 위해 처음 10개 청크만 표시
                                if chunk_count >= 10:
                                    print("... (더 많은 스트리밍 데이터)")
                                    break
                                
                            except json.JSONDecodeError:
                                continue
                    
                    print("-" * 50)
                    print(f"\n📊 스트리밍 분석:")
                    print(f"📦 수신된 청크 수: {chunk_count}")
                    print(f"📝 누적된 코드 길이: {len(received_content)}자")
                    
                    if received_content:
                        print("\n📝 스트리밍으로 받은 코드 미리보기:")
                        print("-" * 30)
                        print(received_content[:200] + "..." if len(received_content) > 200 else received_content)
                        print("-" * 30)
                
                else:
                    print(f"❌ 스트리밍 요청 실패: {response.status_code}")
                
            except Exception as e:
                print(f"❌ 스트리밍 호출 실패: {e}")
    
    async def demo_security_status_check(self):
        """보안 상태 확인 예시"""
        self.print_section("4. 보안 상태 확인 요청/응답 예시")
        
        url = f"{self.base_url}/code/security-status"
        self.print_request("GET", url)
        
        # 실제 API 호출
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.get(url, headers=self.headers)
                response_data = response.json()
                self.print_response(response.status_code, response_data)
                
                # 보안 상태 분석
                print("\n📊 보안 시스템 분석:")
                security_system = response_data.get("security_system", {})
                security_tests = response_data.get("security_tests", {})
                security_features = response_data.get("security_features", {})
                
                print(f"🔒 보안 시스템 상태: {security_system.get('status', 'unknown')}")
                print(f"🛡️ 검증기 로드 상태: {'로드됨' if security_system.get('validator_loaded') else '미로드'}")
                print(f"🤖 AI 모델 상태: {'로드됨' if security_system.get('model_loaded') else '미로드'}")
                
                # 보안 테스트 결과
                safe_test = security_tests.get("safe_input_test", {})
                unsafe_test = security_tests.get("unsafe_input_test", {})
                
                print(f"\n🧪 보안 테스트 결과:")
                print(f"   ✅ 안전한 입력 테스트: {'통과' if safe_test.get('passed') else '실패'}")
                print(f"   🚨 위험한 입력 테스트: {'차단됨' if unsafe_test.get('blocked') else '통과됨'}")
                print(f"   🔍 감지된 이슈 수: {unsafe_test.get('issues_detected', 0)}")
                
                # 보안 기능 목록
                print(f"\n🛡️ 활성화된 보안 기능:")
                for feature, enabled in security_features.items():
                    status = "✅" if enabled else "❌"
                    feature_name = feature.replace("_", " ").title()
                    print(f"   {status} {feature_name}")
                
            except Exception as e:
                print(f"❌ API 호출 실패: {e}")
    
    async def demo_security_test(self):
        """보안 테스트 API 예시"""
        self.print_section("5. 보안 테스트 API 요청/응답 예시")
        
        # 보안 테스트 요청 예시
        test_cases = [
            {
                "name": "안전한 코드",
                "test_input": "def hello_world(): print('Hello, World!')"
            },
            {
                "name": "위험한 시스템 명령",
                "test_input": "import os; os.system('rm -rf /')"
            },
            {
                "name": "SQL 인젝션 시도",
                "test_input": "'; DROP TABLE users; --"
            }
        ]
        
        url = f"{self.base_url}/code/security-test"
        
        for test_case in test_cases:
            print(f"\n🔍 테스트 케이스: {test_case['name']}")
            print("-" * 60)
            
            request_payload = {"test_input": test_case["test_input"]}
            self.print_request("POST", url, request_payload)
            
            # 실제 API 호출
            async with httpx.AsyncClient(timeout=30.0) as client:
                try:
                    response = await client.post(url, json=request_payload, headers=self.headers)
                    response_data = response.json()
                    
                    # 응답을 간략하게 표시
                    simplified_response = {
                        "test_input": response_data.get("test_input", "")[:50] + "...",
                        "overall_safety": response_data.get("overall_safety", {}),
                        "validation_summary": {
                            "input_issues": response_data.get("validation_results", {}).get("input_validation", {}).get("issue_count", 0),
                            "code_issues": response_data.get("validation_results", {}).get("code_validation", {}).get("issue_count", 0)
                        }
                    }
                    
                    self.print_response(response.status_code, simplified_response)
                    
                    # 보안 테스트 결과 분석
                    overall_safety = response_data.get("overall_safety", {})
                    is_safe = overall_safety.get("is_safe", False)
                    risk_level = overall_safety.get("risk_level", "unknown")
                    recommendation = overall_safety.get("recommendation", "unknown")
                    
                    print(f"\n📊 보안 테스트 분석:")
                    print(f"🔒 안전성: {'안전' if is_safe else '위험'}")
                    print(f"⚠️ 위험도: {risk_level}")
                    print(f"💡 권장사항: {recommendation}")
                    
                except Exception as e:
                    print(f"❌ API 호출 실패: {e}")
    
    async def run_all_demos(self):
        """모든 데모 실행"""
        print("🚀 HAPA AI 모델 호출 흐름 예시 요청/응답 데모")
        print(f"실행 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("기본 URL:", self.base_url)
        print("API Key:", f"{self.api_key[:20]}...")
        
        demos = [
            self.demo_safe_code_generation,
            self.demo_dangerous_input_blocking,
            self.demo_streaming_generation,
            self.demo_security_status_check,
            self.demo_security_test
        ]
        
        for demo in demos:
            try:
                await demo()
                await asyncio.sleep(1)  # 잠깐 대기
            except Exception as e:
                print(f"❌ 데모 실행 중 오류: {e}")
        
        print("\n" + "=" * 80)
        print("🎉 모든 데모가 완료되었습니다!")
        print("=" * 80)
        
        print("\n📋 요약:")
        print("1. ✅ 정상적인 코드 생성 - 안전한 입력에 대한 성공적인 코드 생성")
        print("2. 🚨 위험한 입력 차단 - 보안 위협 감지 및 차단")
        print("3. 📡 스트리밍 응답 - 실시간 토큰 단위 코드 생성")
        print("4. 🔒 보안 상태 확인 - 시스템 보안 기능 상태 점검")
        print("5. 🧪 보안 테스트 - 다양한 입력에 대한 보안 검증")
        
        print("\n💡 주요 특징:")
        print("• 입력/출력 모두에 대한 다단계 안전성 검증")
        print("• 실시간 스트리밍을 통한 향상된 사용자 경험")
        print("• 상세한 보안 정보 및 메타데이터 제공")
        print("• 코드 품질 평가 및 피드백")

async def main():
    """메인 실행 함수"""
    demo = HAPAAPIDemo()
    await demo.run_all_demos()

if __name__ == "__main__":
    asyncio.run(main()) 