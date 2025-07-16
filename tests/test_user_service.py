import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.services.user_service import UserService, user_service
import httpx

class TestUserService:
    """사용자 서비스 테스트 클래스"""
    
    @pytest.fixture
    def user_service_instance(self):
        """테스트용 사용자 서비스 인스턴스"""
        return UserService()
    
    @pytest.fixture
    def mock_httpx_client(self):
        """Mock HTTPX 클라이언트"""
        mock_client = AsyncMock()
        return mock_client
    
    @pytest.fixture
    def sample_user_data(self):
        """테스트용 사용자 데이터"""
        return {
            "email": "test@example.com",
            "username": "testuser"
        }
    
    @pytest.fixture
    def sample_jwt_token(self):
        """테스트용 JWT 토큰"""
        return "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.test.token"
    
    @pytest.fixture
    def sample_settings_data(self):
        """테스트용 설정 데이터"""
        return [
            {"id": 1, "setting_type": "skill_level", "option_value": "intermediate"},
            {"id": 2, "setting_type": "code_style", "option_value": "standard"},
            {"id": 3, "setting_type": "comment_style", "option_value": "detailed"}
        ]
    
    def test_user_service_initialization(self, user_service_instance):
        """사용자 서비스 초기화 테스트"""
        assert user_service_instance.db_module_url == "http://localhost:8001"
        assert user_service_instance.timeout is not None
    
    @pytest.mark.asyncio
    async def test_login_or_register_success(self, user_service_instance, sample_user_data):
        """로그인/회원가입 성공 테스트"""
        expected_response = {
            "access_token": "test_token_123",
            "token_type": "bearer"
        }
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = expected_response
        
        with patch('httpx.AsyncClient') as mock_async_client:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_async_client.return_value.__aenter__.return_value = mock_client
            
            result = await user_service_instance.login_or_register(
                sample_user_data["email"], 
                sample_user_data["username"]
            )
            
            assert result == expected_response
            mock_client.post.assert_called_once_with(
                "http://localhost:8001/login",
                json=sample_user_data
            )
    
    @pytest.mark.asyncio
    async def test_login_or_register_without_username(self, user_service_instance):
        """사용자명 없이 로그인/회원가입 테스트"""
        email = "test@example.com"
        expected_username = "test"  # 이메일에서 추출된 사용자명
        
        expected_response = {
            "access_token": "test_token_123",
            "token_type": "bearer"
        }
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = expected_response
        
        with patch('httpx.AsyncClient') as mock_async_client:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_async_client.return_value.__aenter__.return_value = mock_client
            
            result = await user_service_instance.login_or_register(email)
            
            assert result == expected_response
            # 사용자명이 이메일에서 자동 생성되었는지 확인
            call_args = mock_client.post.call_args
            assert call_args[1]["json"]["username"] == expected_username
    
    @pytest.mark.asyncio
    async def test_login_or_register_failure(self, user_service_instance, sample_user_data):
        """로그인/회원가입 실패 테스트"""
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "Bad Request"
        
        with patch('httpx.AsyncClient') as mock_async_client:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_async_client.return_value.__aenter__.return_value = mock_client
            
            result = await user_service_instance.login_or_register(
                sample_user_data["email"], 
                sample_user_data["username"]
            )
            
            assert result is None
    
    @pytest.mark.asyncio
    async def test_login_or_register_network_error(self, user_service_instance, sample_user_data):
        """네트워크 오류 시 로그인/회원가입 테스트"""
        with patch('httpx.AsyncClient') as mock_async_client:
            mock_client = AsyncMock()
            mock_client.post.side_effect = httpx.RequestError("Network error")
            mock_async_client.return_value.__aenter__.return_value = mock_client
            
            result = await user_service_instance.login_or_register(
                sample_user_data["email"], 
                sample_user_data["username"]
            )
            
            assert result is None
    
    @pytest.mark.asyncio
    async def test_get_user_settings_success(self, user_service_instance, sample_jwt_token, sample_settings_data):
        """사용자 설정 조회 성공 테스트"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = sample_settings_data
        
        with patch('httpx.AsyncClient') as mock_async_client:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_async_client.return_value.__aenter__.return_value = mock_client
            
            result = await user_service_instance.get_user_settings(sample_jwt_token)
            
            assert result == sample_settings_data
            mock_client.get.assert_called_once_with(
                "http://localhost:8001/users/me/settings",
                headers={"Authorization": f"Bearer {sample_jwt_token}"}
            )
    
    @pytest.mark.asyncio
    async def test_get_user_settings_unauthorized(self, user_service_instance, sample_jwt_token):
        """인증 실패 시 사용자 설정 조회 테스트"""
        mock_response = MagicMock()
        mock_response.status_code = 401
        
        with patch('httpx.AsyncClient') as mock_async_client:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_async_client.return_value.__aenter__.return_value = mock_client
            
            result = await user_service_instance.get_user_settings(sample_jwt_token)
            
            assert result is None
    
    @pytest.mark.asyncio
    async def test_update_user_settings_success(self, user_service_instance, sample_jwt_token):
        """사용자 설정 업데이트 성공 테스트"""
        option_ids = [1, 2, 3, 4, 5]
        
        mock_response = MagicMock()
        mock_response.status_code = 204
        
        with patch('httpx.AsyncClient') as mock_async_client:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_async_client.return_value.__aenter__.return_value = mock_client
            
            result = await user_service_instance.update_user_settings(sample_jwt_token, option_ids)
            
            assert result is True
            mock_client.post.assert_called_once_with(
                "http://localhost:8001/users/me/settings",
                json={"option_ids": option_ids},
                headers={"Authorization": f"Bearer {sample_jwt_token}"}
            )
    
    @pytest.mark.asyncio
    async def test_update_user_settings_failure(self, user_service_instance, sample_jwt_token):
        """사용자 설정 업데이트 실패 테스트"""
        option_ids = [1, 2, 3]
        
        mock_response = MagicMock()
        mock_response.status_code = 400
        
        with patch('httpx.AsyncClient') as mock_async_client:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_async_client.return_value.__aenter__.return_value = mock_client
            
            result = await user_service_instance.update_user_settings(sample_jwt_token, option_ids)
            
            assert result is False
    
    @pytest.mark.asyncio
    async def test_get_setting_options_success(self, user_service_instance, sample_jwt_token):
        """설정 옵션 조회 성공 테스트"""
        options_data = [
            {"id": 1, "setting_type": "skill_level", "option_value": "beginner"},
            {"id": 2, "setting_type": "skill_level", "option_value": "intermediate"},
            {"id": 3, "setting_type": "skill_level", "option_value": "advanced"}
        ]
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = options_data
        
        with patch('httpx.AsyncClient') as mock_async_client:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_async_client.return_value.__aenter__.return_value = mock_client
            
            result = await user_service_instance.get_setting_options(sample_jwt_token)
            
            assert result == options_data
            mock_client.get.assert_called_once_with(
                "http://localhost:8001/settings/options",
                headers={"Authorization": f"Bearer {sample_jwt_token}"}
            )
    
    @pytest.mark.asyncio
    async def test_get_user_info_success(self, user_service_instance, sample_jwt_token):
        """사용자 정보 조회 성공 테스트"""
        user_info = {
            "id": 1,
            "email": "test@example.com",
            "username": "testuser"
        }
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = user_info
        
        with patch('httpx.AsyncClient') as mock_async_client:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_async_client.return_value.__aenter__.return_value = mock_client
            
            result = await user_service_instance.get_user_info(sample_jwt_token)
            
            assert result == user_info
            mock_client.get.assert_called_once_with(
                "http://localhost:8001/users/me",
                headers={"Authorization": f"Bearer {sample_jwt_token}"}
            )
    
    @pytest.mark.asyncio
    async def test_save_user_profile_success(self, user_service_instance, sample_jwt_token):
        """사용자 프로필 저장 성공 테스트"""
        profile_data = {
            "pythonSkillLevel": "intermediate",
            "codeOutputStructure": "standard",
            "explanationStyle": "detailed"
        }
        option_ids = [2, 6, 10]
        
        # update_user_settings 메서드를 Mock
        with patch.object(user_service_instance, 'update_user_settings', return_value=True) as mock_update:
            result = await user_service_instance.save_user_profile(
                sample_jwt_token, 
                profile_data, 
                option_ids
            )
            
            assert result is True
            mock_update.assert_called_once_with(sample_jwt_token, option_ids)
    
    @pytest.mark.asyncio
    async def test_save_user_profile_failure(self, user_service_instance, sample_jwt_token):
        """사용자 프로필 저장 실패 테스트"""
        profile_data = {"skill": "intermediate"}
        option_ids = [1, 2, 3]
        
        # update_user_settings 메서드를 Mock (실패)
        with patch.object(user_service_instance, 'update_user_settings', return_value=False) as mock_update:
            result = await user_service_instance.save_user_profile(
                sample_jwt_token, 
                profile_data, 
                option_ids
            )
            
            assert result is False
            mock_update.assert_called_once_with(sample_jwt_token, option_ids)
    
    @pytest.mark.asyncio
    async def test_save_user_profile_exception(self, user_service_instance, sample_jwt_token):
        """사용자 프로필 저장 예외 처리 테스트"""
        profile_data = {"skill": "intermediate"}
        option_ids = [1, 2, 3]
        
        # update_user_settings 메서드에서 예외 발생
        with patch.object(user_service_instance, 'update_user_settings', side_effect=Exception("Database error")):
            result = await user_service_instance.save_user_profile(
                sample_jwt_token, 
                profile_data, 
                option_ids
            )
            
            assert result is False


class TestUserServiceModule:
    """사용자 서비스 모듈 레벨 테스트"""
    
    def test_global_user_service_instance(self):
        """글로벌 사용자 서비스 인스턴스 테스트"""
        assert user_service is not None
        assert isinstance(user_service, UserService)
        assert user_service.db_module_url == "http://localhost:8001"
    
    @pytest.mark.asyncio
    async def test_concurrent_requests(self):
        """동시 요청 처리 테스트"""
        import asyncio
        
        async def mock_request():
            # Mock HTTP 요청을 시뮬레이션
            return {"status": "success"}
        
        # 여러 동시 요청 시뮬레이션
        with patch.object(user_service, 'login_or_register', side_effect=mock_request):
            tasks = [
                user_service.login_or_register(f"user{i}@test.com") 
                for i in range(5)
            ]
            results = await asyncio.gather(*tasks)
            
            assert len(results) == 5
            for result in results:
                assert result["status"] == "success"


class TestUserServiceErrorHandling:
    """사용자 서비스 에러 처리 테스트"""
    
    @pytest.mark.asyncio
    async def test_timeout_handling(self, user_service_instance):
        """타임아웃 처리 테스트"""
        with patch('httpx.AsyncClient') as mock_async_client:
            mock_client = AsyncMock()
            mock_client.post.side_effect = httpx.TimeoutException("Request timeout")
            mock_async_client.return_value.__aenter__.return_value = mock_client
            
            result = await user_service_instance.login_or_register("test@example.com")
            
            assert result is None
    
    @pytest.mark.asyncio
    async def test_invalid_response_format(self, user_service_instance, sample_jwt_token):
        """잘못된 응답 형식 처리 테스트"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.side_effect = ValueError("Invalid JSON")
        
        with patch('httpx.AsyncClient') as mock_async_client:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_async_client.return_value.__aenter__.return_value = mock_client
            
            result = await user_service_instance.get_user_settings(sample_jwt_token)
            
            assert result is None
    
    @pytest.mark.asyncio
    async def test_connection_error(self, user_service_instance):
        """연결 오류 처리 테스트"""
        with patch('httpx.AsyncClient') as mock_async_client:
            mock_client = AsyncMock()
            mock_client.post.side_effect = httpx.ConnectError("Connection failed")
            mock_async_client.return_value.__aenter__.return_value = mock_client
            
            result = await user_service_instance.login_or_register("test@example.com")
            
            assert result is None


if __name__ == "__main__":
    pytest.main([__file__]) 