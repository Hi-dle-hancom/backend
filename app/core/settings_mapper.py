"""
HAPA 개인화 설정 매핑 중앙 관리 모듈
모든 설정 옵션 ID와 매핑 로직을 중앙화하여 유지보수성 향상
"""

import logging
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class SettingCategory(Enum):
    """설정 카테고리"""

    PYTHON_SKILL = "python_skill_level"
    CODE_OUTPUT = "code_output_structure"
    EXPLANATION = "explanation_style"
    PROJECT_CONTEXT = "project_context"
    COMMENT_TRIGGER = "comment_trigger_mode"
    LANGUAGE_FEATURES = "language_features"
    ERROR_HANDLING = "error_handling_preference"


class SettingsMapper:
    """설정 옵션 ID와 값 매핑을 담당하는 중앙 클래스"""

    # 설정 옵션 ID 매핑 (DB 스키마와 일치)
    OPTION_ID_MAPPING = {
        # Python 스킬 수준 (ID: 1-4)
        SettingCategory.PYTHON_SKILL: {
            1: "beginner",
            2: "intermediate",
            3: "advanced",
            4: "expert",
        },
        # 코드 출력 구조 (ID: 5-8)
        SettingCategory.CODE_OUTPUT: {
            5: "minimal",
            6: "standard",
            7: "detailed",
            8: "comprehensive",
        },
        # 설명 스타일 (ID: 9-12)
        SettingCategory.EXPLANATION: {
            9: "brief",
            10: "standard",
            11: "detailed",
            12: "educational",
        },
        # 프로젝트 컨텍스트 (ID: 13-16)
        SettingCategory.PROJECT_CONTEXT: {
            13: "web_development",
            14: "data_science",
            15: "automation",
            16: "general_purpose",
        },
        # 주석 트리거 모드 (ID: 17-20)
        SettingCategory.COMMENT_TRIGGER: {
            17: "immediate",
            18: "sidebar",
            19: "confirm",
            20: "preview",
        },
        # 선호 언어 기능 (ID: 21-24)
        SettingCategory.LANGUAGE_FEATURES: {
            21: "type_hints",
            22: "dataclasses",
            23: "async_await",
            24: "f_strings",
        },
        # 에러 처리 선호도 (ID: 25-27)
        SettingCategory.ERROR_HANDLING: {25: "basic", 26: "detailed", 27: "robust"},
    }

    # 역매핑: 값 → ID
    VALUE_TO_ID_MAPPING = {}

    # camelCase ↔ snake_case 변환 매핑
    CAMEL_TO_SNAKE_MAPPING = {
        "pythonSkillLevel": "skill_level",
        "codeOutputStructure": "code_style",
        "explanationStyle": "comment_style",
        "projectContext": "project_context",
        "commentTriggerMode": "trigger_mode",
        "preferredLanguageFeatures": "language_features",
        "errorHandlingPreference": "error_handling",
    }

    SNAKE_TO_CAMEL_MAPPING = {v: k for k, v in CAMEL_TO_SNAKE_MAPPING.items()}

    def __init__(self):
        # 역매핑 테이블 생성
        self._build_reverse_mapping()

    def _build_reverse_mapping(self):
        """값 → ID 역매핑 테이블 구축"""
        for category, id_value_map in self.OPTION_ID_MAPPING.items():
            self.VALUE_TO_ID_MAPPING[category] = {
                v: k for k, v in id_value_map.items()}

    def map_db_settings_to_preferences(
        self, db_settings: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """DB 설정을 사용자 선호도로 변환"""
        preferences = self.get_default_preferences()

        try:
            # 언어 기능은 빈 리스트로 시작 (중복 방지)
            preferences["language_features"] = []

            for setting in db_settings:
                option_id = setting.get("option_id")
                if not option_id:
                    continue

                # 각 카테고리별로 매핑
                for category, id_map in self.OPTION_ID_MAPPING.items():
                    if option_id in id_map:
                        value = id_map[option_id]

                        if category == SettingCategory.PYTHON_SKILL:
                            preferences["skill_level"] = value
                        elif category == SettingCategory.CODE_OUTPUT:
                            preferences["code_style"] = value
                        elif category == SettingCategory.EXPLANATION:
                            preferences["comment_style"] = value
                        elif category == SettingCategory.PROJECT_CONTEXT:
                            preferences["project_context"] = value
                        elif category == SettingCategory.COMMENT_TRIGGER:
                            preferences["trigger_mode"] = value
                        elif category == SettingCategory.LANGUAGE_FEATURES:
                            # 중복 없이 추가
                            if value not in preferences["language_features"]:
                                preferences["language_features"].append(value)
                        elif category == SettingCategory.ERROR_HANDLING:
                            preferences["error_handling"] = value

                        break

            # 언어 기능이 비어있으면 기본값 설정
            if not preferences["language_features"]:
                preferences["language_features"] = ["type_hints", "f_strings"]

            logger.info(f"DB 설정 매핑 완료: {len(db_settings)}개 → 선호도 변환")
            return preferences

        except Exception as e:
            logger.error(f"DB 설정 매핑 실패: {e}")
            return self.get_default_preferences()

    def map_user_profile_to_preferences(
        self, user_profile, base_preferences: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Frontend userProfile을 Backend 선호도로 변환 (camelCase → snake_case)"""
        if base_preferences is None:
            preferences = self.get_default_preferences()
        else:
            preferences = base_preferences.copy()

        try:
            if not user_profile:
                return preferences

            # camelCase → snake_case 안전 변환
            safe_mappings = {
                "pythonSkillLevel": ("skill_level", self._validate_skill_level),
                "codeOutputStructure": ("code_style", self._validate_code_style),
                "explanationStyle": ("comment_style", self._validate_explanation_style),
                "projectContext": ("project_context", self._validate_project_context),
                "commentTriggerMode": ("trigger_mode", self._validate_trigger_mode),
                "errorHandlingPreference": (
                    "error_handling",
                    self._validate_error_handling,
                ),
                "preferredLanguageFeatures": (
                    "language_features",
                    self._validate_language_features,
                ),
            }

            for camel_key, (snake_key, validator) in safe_mappings.items():
                if hasattr(user_profile, camel_key):
                    raw_value = getattr(user_profile, camel_key)
                    validated_value = validator(raw_value)
                    if validated_value is not None:
                        preferences[snake_key] = validated_value

            logger.info("userProfile → 선호도 매핑 완료")
            return preferences

        except Exception as e:
            logger.error(f"userProfile 매핑 실패: {e}")
            return preferences

    def map_onboarding_data_to_option_ids(
        self, onboarding_data: Dict[str, Any]
    ) -> List[int]:
        """온보딩 데이터를 설정 옵션 ID 리스트로 변환"""
        option_ids = []

        try:
            # 스킬 수준
            skill_level = onboarding_data.get("skillLevel", "intermediate")
            skill_id = self._get_id_by_value(
                SettingCategory.PYTHON_SKILL, skill_level)
            if skill_id:
                option_ids.append(skill_id)

            # 코드 출력 구조
            output_structure = onboarding_data.get(
                "outputStructure", "standard")
            output_id = self._get_id_by_value(
                SettingCategory.CODE_OUTPUT, output_structure
            )
            if output_id:
                option_ids.append(output_id)

            # 설명 스타일
            explanation_style = onboarding_data.get(
                "explanationStyle", "standard")
            explanation_id = self._get_id_by_value(
                SettingCategory.EXPLANATION, explanation_style
            )
            if explanation_id:
                option_ids.append(explanation_id)

            # 프로젝트 컨텍스트
            project_context = onboarding_data.get(
                "projectContext", "general_purpose")
            context_id = self._get_id_by_value(
                SettingCategory.PROJECT_CONTEXT, project_context
            )
            if context_id:
                option_ids.append(context_id)

            # 주석 트리거 모드
            trigger_mode = onboarding_data.get("commentTriggerMode", "confirm")
            trigger_id = self._get_id_by_value(
                SettingCategory.COMMENT_TRIGGER, trigger_mode
            )
            if trigger_id:
                option_ids.append(trigger_id)

            # 언어 기능들
            language_features = onboarding_data.get("languageFeatures", [])
            if isinstance(language_features, list):
                for feature in language_features:
                    feature_id = self._get_id_by_value(
                        SettingCategory.LANGUAGE_FEATURES, feature
                    )
                    if feature_id:
                        option_ids.append(feature_id)

            # 에러 처리 선호도
            error_handling = onboarding_data.get("errorHandling", "basic")
            error_id = self._get_id_by_value(
                SettingCategory.ERROR_HANDLING, error_handling
            )
            if error_id:
                option_ids.append(error_id)

            logger.info(f"온보딩 데이터 → 옵션 ID 매핑 완료: {len(option_ids)}개")
            return sorted(list(set(option_ids)))  # 중복 제거 및 정렬

        except Exception as e:
            logger.error(f"온보딩 데이터 매핑 실패: {e}")
            return []

    def _get_id_by_value(
            self,
            category: SettingCategory,
            value: str) -> Optional[int]:
        """카테고리와 값으로 옵션 ID 조회"""
        try:
            return self.VALUE_TO_ID_MAPPING.get(category, {}).get(value)
        except Exception:
            return None

    def get_default_preferences(self) -> Dict[str, Any]:
        """기본 사용자 선호도"""
        return {
            "skill_level": "intermediate",
            "code_style": "standard",
            "project_context": "general_purpose",
            "comment_style": "standard",
            "error_handling": "basic",
            "language_features": ["type_hints", "f_strings"],
            "trigger_mode": "confirm",
        }

    # 검증 함수들
    def _validate_skill_level(self, value) -> Optional[str]:
        valid_levels = ["beginner", "intermediate", "advanced", "expert"]
        return value if value in valid_levels else None

    def _validate_code_style(self, value) -> Optional[str]:
        valid_styles = ["minimal", "standard", "detailed", "comprehensive"]
        return value if value in valid_styles else None

    def _validate_explanation_style(self, value) -> Optional[str]:
        valid_styles = ["brief", "standard", "detailed", "educational"]
        return value if value in valid_styles else None

    def _validate_project_context(self, value) -> Optional[str]:
        valid_contexts = [
            "web_development",
            "data_science",
            "automation",
            "general_purpose",
        ]
        return value if value in valid_contexts else None

    def _validate_trigger_mode(self, value) -> Optional[str]:
        valid_modes = ["immediate", "sidebar", "confirm", "preview"]
        return value if value in valid_modes else None

    def _validate_error_handling(self, value) -> Optional[str]:
        valid_handling = ["basic", "detailed", "robust"]
        return value if value in valid_handling else None

    def _validate_language_features(self, value) -> Optional[List[str]]:
        if not isinstance(value, list):
            return None
        valid_features = [
            "type_hints",
            "dataclasses",
            "async_await",
            "f_strings"]
        validated = [f for f in value if f in valid_features]
        return validated if validated else None


# 전역 싱글톤 인스턴스
settings_mapper = SettingsMapper()


# 편의 함수들
def map_db_to_preferences(db_settings: List[Dict[str, Any]]) -> Dict[str, Any]:
    """DB 설정 → 선호도 변환 (편의 함수)"""
    return settings_mapper.map_db_settings_to_preferences(db_settings)


def map_profile_to_preferences(
    user_profile, base_preferences: Dict[str, Any] = None
) -> Dict[str, Any]:
    """userProfile → 선호도 변환 (편의 함수)"""
    return settings_mapper.map_user_profile_to_preferences(
        user_profile, base_preferences
    )


def map_onboarding_to_ids(onboarding_data: Dict[str, Any]) -> List[int]:
    """온보딩 데이터 → 옵션 ID 변환 (편의 함수)"""
    return settings_mapper.map_onboarding_data_to_option_ids(onboarding_data)


def get_default_user_preferences() -> Dict[str, Any]:
    """기본 사용자 선호도 (편의 함수)"""
    return settings_mapper.get_default_preferences()
