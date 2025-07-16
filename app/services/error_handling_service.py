import json
import logging
import os
import traceback
import uuid
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union

from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError

from app.schemas.error_handling import (
    ClientErrorResponse,
    EnhancedErrorResponse,
    ErrorCategory,
    ErrorContext,
    ErrorPattern,
    ErrorSeverity,
    ErrorSummary,
    RecoveryAction,
    RecoveryGuide,
    ServerErrorResponse,
    StandardErrorCode,
    ValidationErrorDetail,
)

logger = logging.getLogger(__name__)


class ErrorHandlingService:
    """통합 오류 처리 서비스"""

    def __init__(self):
        # 오류 발생 통계 저장
        self.error_stats: Dict[str, Any] = defaultdict(
            lambda: {
                "count": 0,
                "first_seen": None,
                "last_seen": None,
                "affected_users": set(),
                "resolution_times": [],
            }
        )

        # 오류 코드별 복구 가이드 매핑
        self.recovery_guides = self._initialize_recovery_guides()

        # 심각도별 알림 설정
        self.alert_settings = {
            ErrorSeverity.CRITICAL: {"immediate": True, "escalate": True},
            ErrorSeverity.HIGH: {"immediate": True, "escalate": False},
            ErrorSeverity.MEDIUM: {"immediate": False, "escalate": False},
            ErrorSeverity.LOW: {"immediate": False, "escalate": False},
        }

    def handle_validation_error(
        self,
        request: Request,
        exc: RequestValidationError,
        correlation_id: Optional[str] = None,
    ) -> ClientErrorResponse:
        """유효성 검사 오류 처리"""

        # 컨텍스트 정보 수집
        context = self._extract_context(request, correlation_id)

        # 필드별 오류 상세 분석
        validation_errors = []
        field_errors = {}

        for error in exc.errors():
            field_path = ".".join(str(loc) for loc in error["loc"][1:])
            error_msg = error["msg"]
            error_type = error["type"]

            # 상세 오류 정보 생성
            validation_detail = ValidationErrorDetail(
                field=field_path or "root",
                value=error.get(
                    "input",
                    "N/A"),
                constraint=error_type,
                message=error_msg,
                suggestion=self._get_validation_suggestion(
                    error_type,
                    error_msg),
            )
            validation_errors.append(validation_detail)

            # 필드별 오류 그룹화
            if field_path not in field_errors:
                field_errors[field_path] = []
            field_errors[field_path].append(error_msg)

        # 주요 오류 메시지 결정
        main_error = exc.errors()[0] if exc.errors() else {}
        error_message = f"입력 데이터 검증에 실패했습니다: {main_error.get('msg', '알 수 없는 오류')}"

        # 복구 가이드 생성
        recovery_guide = RecoveryGuide(
            actions=[
                RecoveryAction.UPDATE_INPUT,
                RecoveryAction.CHECK_SETTINGS],
            user_message="입력 데이터를 확인하고 다시 시도해주세요.",
            developer_message="요청 파라미터의 타입과 형식을 확인하세요.",
            documentation_url="/docs",
            retry_after=None,
            max_retries=3,
        )

        # 오류 통계 업데이트
        self._update_error_stats(
            StandardErrorCode.VALIDATION_FAILED,
            context.user_id,
            ErrorSeverity.MEDIUM)

        return ClientErrorResponse(
            error_code=StandardErrorCode.VALIDATION_FAILED,
            error_message=error_message,
            category=ErrorCategory.VALIDATION_ERROR,
            severity=ErrorSeverity.MEDIUM,
            details={"total_errors": len(exc.errors())},
            field_errors=field_errors,
            validation_errors=validation_errors,
            context=context,
            recovery_guide=recovery_guide,
            correlation_id=correlation_id,
        )

    def handle_http_exception(
        self, request: Request, exc: HTTPException, correlation_id: Optional[str] = None
    ) -> Union[ClientErrorResponse, ServerErrorResponse]:
        """HTTP 예외 처리"""

        context = self._extract_context(request, correlation_id)

        # 상태 코드로 Client/Server 오류 구분
        is_client_error = 400 <= exc.status_code < 500
        is_server_error = 500 <= exc.status_code < 600

        # 표준 오류 코드 매핑
        error_code = self._map_http_status_to_error_code(exc.status_code)
        severity = self._determine_severity(exc.status_code, str(exc.detail))

        # 복구 가이드 생성
        recovery_guide = self.recovery_guides.get(error_code)

        # 오류 통계 업데이트
        self._update_error_stats(error_code, context.user_id, severity)

        if is_client_error:
            return ClientErrorResponse(
                error_code=error_code,
                error_message=str(exc.detail),
                category=ErrorCategory.CLIENT_ERROR,
                severity=severity,
                details={"status_code": exc.status_code},
                context=context,
                recovery_guide=recovery_guide,
                correlation_id=correlation_id,
            )

        elif is_server_error:
            # 인시던트 ID 생성 (심각한 서버 오류의 경우)
            incident_id = None
            if severity in [ErrorSeverity.HIGH, ErrorSeverity.CRITICAL]:
                incident_id = (
                    f"INC-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8]}"
                )
                logger.critical(f"Critical server error: {incident_id} - {exc.detail}")

            return ServerErrorResponse(
                error_code=error_code,
                error_message="서버에서 문제가 발생했습니다. 잠시 후 다시 시도해주세요.",
                category=ErrorCategory.SERVER_ERROR,
                severity=severity,
                details={"status_code": exc.status_code},
                context=context,
                recovery_guide=recovery_guide,
                incident_id=incident_id,
                correlation_id=correlation_id,
            )

        # 기본 응답 (예상치 못한 상태 코드)
        return ServerErrorResponse(
            error_code=StandardErrorCode.INTERNAL_SERVER_ERROR,
            error_message="알 수 없는 오류가 발생했습니다.",
            category=ErrorCategory.SERVER_ERROR,
            severity=ErrorSeverity.HIGH,
            context=context,
            correlation_id=correlation_id,
        )

    def handle_general_exception(
        self,
        request: Request,
        exc: Exception,
        correlation_id: Optional[str] = None,
        debug_mode: bool = False,
    ) -> ServerErrorResponse:
        """일반 예외 처리"""

        context = self._extract_context(request, correlation_id)

        # 예외 타입별 분류
        error_code = self._classify_exception(exc)
        severity = self._determine_exception_severity(exc)

        # 인시던트 ID 생성
        incident_id = f"INC-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8]}"

        # 디버그 정보 수집
        debug_info = None
        if debug_mode:
            debug_info = {
                "exception_type": type(exc).__name__,
                "exception_message": str(exc),
                "traceback": traceback.format_exc(),
                "locals": self._safe_extract_locals(exc),
            }

        # 상세 로깅
        logger.error(
            f"Unhandled exception: {incident_id}",
            extra={
                "exception_type": type(exc).__name__,
                "exception_message": str(exc),
                "request_path": str(request.url.path),
                "request_method": request.method,
                "correlation_id": correlation_id,
                "user_id": context.user_id,
            },
        )

        # 복구 가이드
        recovery_guide = RecoveryGuide(
            actions=[
                RecoveryAction.WAIT_AND_RETRY,
                RecoveryAction.CONTACT_SUPPORT],
            user_message="일시적인 문제가 발생했습니다. 잠시 후 다시 시도해주세요.",
            developer_message=f"인시던트 ID: {incident_id}로 로그를 확인하세요.",
            retry_after=30,
            max_retries=3,
        )

        # 오류 통계 업데이트
        self._update_error_stats(error_code, context.user_id, severity)

        # 심각도가 높은 경우 알림 발송
        if severity in [ErrorSeverity.HIGH, ErrorSeverity.CRITICAL]:
            self._trigger_alert(error_code, severity, incident_id, context)

        return ServerErrorResponse(
            error_code=error_code,
            error_message="내부 서버 오류가 발생했습니다. 잠시 후 다시 시도해주세요.",
            category=ErrorCategory.SERVER_ERROR,
            severity=severity,
            details={"incident_id": incident_id},
            debug_info=debug_info,
            context=context,
            recovery_guide=recovery_guide,
            incident_id=incident_id,
            correlation_id=correlation_id,
        )

    def get_error_summary(
        self, time_range: timedelta = timedelta(hours=24)
    ) -> ErrorSummary:
        """오류 통계 요약 생성"""

        cutoff_time = datetime.now() - time_range

        # 시간 범위 내 오류들 필터링
        recent_errors = []
        for error_code, stats in self.error_stats.items():
            if stats["last_seen"] and stats["last_seen"] >= cutoff_time:
                recent_errors.append((error_code, stats))

        # 카테고리별 분류
        client_errors = 0
        server_errors = 0
        validation_errors = 0
        critical_errors = 0
        total_errors = 0

        patterns = []

        for error_code, stats in recent_errors:
            count = stats["count"]
            total_errors += count

            # 카테고리 분류
            if error_code.startswith("E4") or error_code.startswith("V"):
                client_errors += count
                if error_code.startswith("V"):
                    validation_errors += count
            elif error_code.startswith("E5") or error_code.startswith("B"):
                server_errors += count

            # 심각한 오류 카운트 (임계치 기반)
            if count > 10:  # 24시간 내 10회 이상 발생한 오류
                critical_errors += 1

            # 패턴 생성
            avg_resolution_time = None
            if stats["resolution_times"]:
                avg_resolution_time = sum(stats["resolution_times"]) / len(
                    stats["resolution_times"]
                )

            patterns.append(
                ErrorPattern(
                    error_code=StandardErrorCode(error_code),
                    count=count,
                    first_seen=stats["first_seen"],
                    last_seen=stats["last_seen"],
                    affected_users=len(stats["affected_users"]),
                    avg_resolution_time=avg_resolution_time,
                )
            )

        # 빈도순 정렬
        patterns.sort(key=lambda x: x.count, reverse=True)

        return ErrorSummary(
            total_errors=total_errors,
            client_errors=client_errors,
            server_errors=server_errors,
            validation_errors=validation_errors,
            critical_errors=critical_errors,
            patterns=patterns[:20],  # 상위 20개 패턴만
            time_range=f"최근 {time_range.total_seconds() / 3600:.1f}시간",
            generated_at=datetime.now(),
        )

    def _extract_context(
        self, request: Request, correlation_id: Optional[str] = None
    ) -> ErrorContext:
        """요청에서 컨텍스트 정보 추출"""
        return ErrorContext(
            request_id=correlation_id or str(uuid.uuid4()),
            endpoint=str(request.url.path),
            method=request.method,
            user_agent=request.headers.get("user-agent"),
            ip_address=request.client.host if request.client else None,
            trace_id=request.headers.get("x-trace-id"),
            correlation_id=correlation_id,
        )

    def _map_http_status_to_error_code(
            self, status_code: int) -> StandardErrorCode:
        """HTTP 상태 코드를 표준 오류 코드로 매핑"""
        mapping = {
            400: StandardErrorCode.INVALID_REQUEST,
            401: StandardErrorCode.UNAUTHORIZED,
            403: StandardErrorCode.FORBIDDEN,
            404: StandardErrorCode.RESOURCE_NOT_FOUND,
            409: StandardErrorCode.CONFLICT,
            422: StandardErrorCode.VALIDATION_FAILED,
            429: StandardErrorCode.RATE_LIMIT_EXCEEDED,
            500: StandardErrorCode.INTERNAL_SERVER_ERROR,
            502: StandardErrorCode.EXTERNAL_API_ERROR,
            503: StandardErrorCode.SERVICE_UNAVAILABLE,
            504: StandardErrorCode.TIMEOUT_ERROR,
        }
        return mapping.get(
            status_code,
            StandardErrorCode.INTERNAL_SERVER_ERROR)

    def _determine_severity(
            self,
            status_code: int,
            detail: str) -> ErrorSeverity:
        """HTTP 상태 코드와 상세 정보로 심각도 결정"""
        if status_code >= 500:
            if "database" in detail.lower() or "timeout" in detail.lower():
                return ErrorSeverity.CRITICAL
            return ErrorSeverity.HIGH
        elif status_code == 429:
            return ErrorSeverity.MEDIUM
        elif status_code in [401, 403]:
            return ErrorSeverity.MEDIUM
        else:
            return ErrorSeverity.LOW

    def _classify_exception(self, exc: Exception) -> StandardErrorCode:
        """예외 타입으로 오류 코드 분류"""
        if isinstance(exc, (ConnectionError, TimeoutError)):
            return StandardErrorCode.EXTERNAL_API_ERROR
        elif isinstance(exc, MemoryError):
            return StandardErrorCode.INSUFFICIENT_RESOURCES
        elif "database" in str(exc).lower():
            return StandardErrorCode.DATABASE_ERROR
        else:
            return StandardErrorCode.INTERNAL_SERVER_ERROR

    def _determine_exception_severity(self, exc: Exception) -> ErrorSeverity:
        """예외 타입으로 심각도 결정"""
        if isinstance(exc, (MemoryError, SystemError)):
            return ErrorSeverity.CRITICAL
        elif isinstance(exc, (ConnectionError, TimeoutError)):
            return ErrorSeverity.HIGH
        else:
            return ErrorSeverity.MEDIUM

    def _get_validation_suggestion(
        self, error_type: str, error_msg: str
    ) -> Optional[str]:
        """유효성 검사 오류에 대한 수정 제안"""
        suggestions = {
            "missing": "필수 필드를 입력해주세요.",
            "type_error": "올바른 데이터 타입을 입력해주세요.",
            "value_error": "유효한 값을 입력해주세요.",
            "string_too_short": "최소 길이를 확인해주세요.",
            "string_too_long": "최대 길이를 확인해주세요.",
            "greater_than": "최솟값을 확인해주세요.",
            "less_than": "최댓값을 확인해주세요.",
        }

        for key, suggestion in suggestions.items():
            if key in error_type.lower():
                return suggestion

        return "입력 형식을 확인해주세요."

    def _safe_extract_locals(self, exc: Exception) -> Dict[str, Any]:
        """안전하게 예외 발생 지점의 로컬 변수 추출"""
        try:
            tb = exc.__traceback__
            if tb and tb.tb_frame:
                locals_dict = {}
                for key, value in tb.tb_frame.f_locals.items():
                    try:
                        # 직렬화 가능한 것만 추출
                        json.dumps(value, default=str)
                        locals_dict[key] = str(value)[:200]  # 길이 제한
                    except BaseException:
                        locals_dict[key] = f"<{type(value).__name__}>"
                return locals_dict
        except BaseException:
            pass

        return {}

    def _update_error_stats(
        self,
        error_code: StandardErrorCode,
        user_id: Optional[str],
        severity: ErrorSeverity,
    ):
        """오류 통계 업데이트"""
        now = datetime.now()
        stats = self.error_stats[error_code.value]

        stats["count"] += 1
        stats["last_seen"] = now
        if stats["first_seen"] is None:
            stats["first_seen"] = now

        if user_id:
            stats["affected_users"].add(user_id)

    def _trigger_alert(
        self,
        error_code: StandardErrorCode,
        severity: ErrorSeverity,
        incident_id: str,
        context: ErrorContext,
    ):
        """심각한 오류 발생 시 알림 발송"""
        alert_config = self.alert_settings.get(severity, {})

        if alert_config.get("immediate"):
            logger.critical(
                f"ALERT: {severity.value.upper()} error detected",
                extra={
                    "error_code": error_code.value,
                    "incident_id": incident_id,
                    "endpoint": context.endpoint,
                    "user_id": context.user_id,
                    "timestamp": context.timestamp.isoformat(),
                },
            )

            # 실제 알림 발송 구현
            self._send_alert_notifications(
                error_code, severity, incident_id, context)

    def _send_alert_notifications(
        self,
        error_code: StandardErrorCode,
        severity: ErrorSeverity,
        incident_id: str,
        context: ErrorContext,
    ):
        """실제 알림 채널로 알림 발송"""
        try:
            alert_message = self._create_alert_message(
                error_code, severity, incident_id, context
            )

            # 환경변수 기반 알림 채널 선택
            import os

            # 1. Slack 알림 (웹훅 URL이 설정된 경우)
            slack_webhook = os.getenv("SLACK_WEBHOOK_URL")
            if slack_webhook and severity in [
                ErrorSeverity.CRITICAL,
                ErrorSeverity.HIGH,
            ]:
                self._send_slack_alert(slack_webhook, alert_message, severity)

            # 2. Discord 알림 (웹훅 URL이 설정된 경우)
            discord_webhook = os.getenv("DISCORD_WEBHOOK_URL")
            if discord_webhook and severity == ErrorSeverity.CRITICAL:
                self._send_discord_alert(
                    discord_webhook, alert_message, severity)

            # 3. 이메일 알림 (SMTP 설정이 된 경우)
            smtp_config = {
                "host": os.getenv("SMTP_HOST"),
                "port": os.getenv("SMTP_PORT", "587"),
                "username": os.getenv("SMTP_USERNAME"),
                "password": os.getenv("SMTP_PASSWORD"),
                "to_emails": os.getenv("ALERT_EMAILS", "").split(","),
            }
            if (
                all(
                    [
                        smtp_config["host"],
                        smtp_config["username"],
                        smtp_config["password"],
                    ]
                )
                and smtp_config["to_emails"]
            ):
                self._send_email_alert(smtp_config, alert_message, severity)

            # 4. 파일 로그 알림 (항상 실행)
            self._log_alert_to_file(alert_message, severity, incident_id)

            logger.info(f"알림 발송 완료: {incident_id} ({severity.value})")

        except Exception as e:
            logger.error(f"알림 발송 실패: {e}", extra={"incident_id": incident_id})

    def _create_alert_message(
        self,
        error_code: StandardErrorCode,
        severity: ErrorSeverity,
        incident_id: str,
        context: ErrorContext,
    ) -> dict:
        """알림 메시지 생성"""
        emoji_map = {
            ErrorSeverity.CRITICAL: "🚨",
            ErrorSeverity.HIGH: "⚠️",
            ErrorSeverity.MEDIUM: "🔶",
            ErrorSeverity.LOW: "ℹ️",
        }

        return {
            "title": f"{emoji_map.get(severity, '🔔')} HAPA 시스템 알림 - {severity.value.upper()}",
            "incident_id": incident_id,
            "error_code": error_code.value,
            "severity": severity.value,
            "endpoint": context.endpoint,
            "timestamp": context.timestamp.isoformat(),
            "user_id": context.user_id,
            "ip_address": context.ip_address,
            "user_agent": context.user_agent,
            "environment": os.getenv("ENVIRONMENT", "unknown"),
        }

    def _send_slack_alert(
        self, webhook_url: str, message: dict, severity: ErrorSeverity
    ):
        """Slack 웹훅으로 알림 발송"""
        try:
            import requests

            color_map = {
                ErrorSeverity.CRITICAL: "#FF0000",
                ErrorSeverity.HIGH: "#FF6600",
                ErrorSeverity.MEDIUM: "#FFCC00",
                ErrorSeverity.LOW: "#0099FF",
            }

            slack_payload = {
                "username": "HAPA Alert Bot",
                "icon_emoji": ":warning:",
                "attachments": [
                    {
                        "color": color_map.get(severity, "#808080"),
                        "title": message["title"],
                        "fields": [
                            {
                                "title": "Incident ID",
                                "value": message["incident_id"],
                                "short": True,
                            },
                            {
                                "title": "Error Code",
                                "value": message["error_code"],
                                "short": True,
                            },
                            {
                                "title": "Endpoint",
                                "value": message["endpoint"],
                                "short": True,
                            },
                            {
                                "title": "Environment",
                                "value": message["environment"],
                                "short": True,
                            },
                            {
                                "title": "Timestamp",
                                "value": message["timestamp"],
                                "short": False,
                            },
                        ],
                        "footer": "HAPA Monitoring System",
                        "ts": int(datetime.now().timestamp()),
                    }
                ],
            }

            response = requests.post(
                webhook_url, json=slack_payload, timeout=10)
            response.raise_for_status()

        except Exception as e:
            logger.error(f"Slack 알림 발송 실패: {e}")

    def _send_discord_alert(
        self, webhook_url: str, message: dict, severity: ErrorSeverity
    ):
        """Discord 웹훅으로 알림 발송"""
        try:
            import requests

            color_map = {
                ErrorSeverity.CRITICAL: 0xFF0000,
                ErrorSeverity.HIGH: 0xFF6600,
                ErrorSeverity.MEDIUM: 0xFFCC00,
                ErrorSeverity.LOW: 0x0099FF,
            }

            discord_payload = {
                "username": "HAPA Alert",
                "avatar_url": "https://example.com/hapa-bot-avatar.png",
                "embeds": [
                    {
                        "title": message["title"],
                        "color": color_map.get(severity, 0x808080),
                        "fields": [
                            {
                                "name": "Incident ID",
                                "value": message["incident_id"],
                                "inline": True,
                            },
                            {
                                "name": "Error Code",
                                "value": message["error_code"],
                                "inline": True,
                            },
                            {
                                "name": "Endpoint",
                                "value": message["endpoint"],
                                "inline": True,
                            },
                            {
                                "name": "Environment",
                                "value": message["environment"],
                                "inline": True,
                            },
                        ],
                        "timestamp": message["timestamp"],
                        "footer": {"text": "HAPA Monitoring System"},
                    }
                ],
            }

            response = requests.post(
                webhook_url, json=discord_payload, timeout=10)
            response.raise_for_status()

        except Exception as e:
            logger.error(f"Discord 알림 발송 실패: {e}")

    def _send_email_alert(
        self, smtp_config: dict, message: dict, severity: ErrorSeverity
    ):
        """SMTP로 이메일 알림 발송"""
        try:
            import smtplib
            from email.mime.multipart import MIMEMultipart
            from email.mime.text import MIMEText

            # 이메일 생성
            msg = MIMEMultipart()
            msg["From"] = smtp_config["username"]
            msg["To"] = ", ".join(smtp_config["to_emails"])
            msg["Subject"] = (
                f"[HAPA Alert] {message['severity'].upper()} - {message['error_code']}"
            )

            # HTML 본문 생성
            html_body = f"""
            <html>
                <body>
                    <h2 style="color: red;">{message['title']}</h2>
                    <table border="1" cellpadding="5">
                        <tr><td><strong>Incident ID</strong></td><td>{message['incident_id']}</td></tr>
                        <tr><td><strong>Error Code</strong></td><td>{message['error_code']}</td></tr>
                        <tr><td><strong>Severity</strong></td><td>{message['severity']}</td></tr>
                        <tr><td><strong>Endpoint</strong></td><td>{message['endpoint']}</td></tr>
                        <tr><td><strong>Environment</strong></td><td>{message['environment']}</td></tr>
                        <tr><td><strong>Timestamp</strong></td><td>{message['timestamp']}</td></tr>
                        <tr><td><strong>User ID</strong></td><td>{message.get('user_id', 'N/A')}</td></tr>
                        <tr><td><strong>IP Address</strong></td><td>{message.get('ip_address', 'N/A')}</td></tr>
                    </table>
                    <p><em>자동 생성된 알림입니다. HAPA 모니터링 시스템에서 발송되었습니다.</em></p>
                </body>
            </html>
            """

            msg.attach(MIMEText(html_body, "html"))

            # SMTP 서버 연결 및 발송
            with smtplib.SMTP(smtp_config["host"], int(smtp_config["port"])) as server:
                server.starttls()
                server.login(smtp_config["username"], smtp_config["password"])
                server.send_message(msg)

        except Exception as e:
            logger.error(f"이메일 알림 발송 실패: {e}")

    def _log_alert_to_file(
        self, message: dict, severity: ErrorSeverity, incident_id: str
    ):
        """파일로 알림 로그 저장"""
        try:
            log_file = f"logs/alerts_{datetime.now().strftime('%Y%m%d')}.log"
            os.makedirs(os.path.dirname(log_file), exist_ok=True)

            with open(log_file, "a", encoding="utf-8") as f:
                log_entry = f"[{message['timestamp']}] {severity.value.upper()} - {incident_id} - {message['error_code']} - {message['endpoint']}\n"
                f.write(log_entry)

        except Exception as e:
            logger.error(f"알림 파일 로그 저장 실패: {e}")

    def _initialize_recovery_guides(
            self) -> Dict[StandardErrorCode, RecoveryGuide]:
        """복구 가이드 초기화"""
        return {
            StandardErrorCode.INVALID_REQUEST: RecoveryGuide(
                actions=[
                    RecoveryAction.UPDATE_INPUT,
                    RecoveryAction.CHECK_SETTINGS],
                user_message="요청 형식을 확인하고 다시 시도해주세요.",
                documentation_url="/docs",
                max_retries=3,
            ),
            StandardErrorCode.UNAUTHORIZED: RecoveryGuide(
                actions=[
                    RecoveryAction.CHECK_SETTINGS],
                user_message="인증 정보를 확인해주세요.",
                developer_message="API 키 또는 토큰을 확인하세요.",
                documentation_url="/docs/authentication",
            ),
            StandardErrorCode.RATE_LIMIT_EXCEEDED: RecoveryGuide(
                actions=[
                    RecoveryAction.WAIT_AND_RETRY],
                user_message="요청 한도를 초과했습니다. 잠시 후 다시 시도해주세요.",
                retry_after=60,
                max_retries=3,
            ),
            StandardErrorCode.INTERNAL_SERVER_ERROR: RecoveryGuide(
                actions=[
                    RecoveryAction.WAIT_AND_RETRY,
                    RecoveryAction.CONTACT_SUPPORT],
                user_message="서버에 일시적인 문제가 발생했습니다.",
                retry_after=30,
                max_retries=3,
            ),
        }


# 전역 서비스 인스턴스
error_handling_service = ErrorHandlingService()
