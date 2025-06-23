-- HAPA 온보딩 설정 옵션 초기화
-- 이 파일은 Docker compose로 PostgreSQL 실행 시 자동으로 실행됩니다.

-- 설정 옵션 테이블이 없다면 생성
CREATE TABLE IF NOT EXISTS setting_options (
    id SERIAL PRIMARY KEY,
    setting_type VARCHAR(100) NOT NULL,
    option_value VARCHAR(100) NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 사용자-설정 매핑 테이블이 없다면 생성  
CREATE TABLE IF NOT EXISTS user_selected_options (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    option_id INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (option_id) REFERENCES setting_options(id) ON DELETE CASCADE
);

-- 사용자 테이블이 없다면 생성
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    username VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 기존 데이터 삭제 (재초기화용)
DELETE FROM user_selected_options;
DELETE FROM setting_options;

-- 온보딩 설정 옵션 데이터 삽입
-- Python 스킬 수준 (ID: 1-4)
INSERT INTO setting_options (id, setting_type, option_value, description) VALUES
(1, 'python_skill_level', 'beginner', 'Python을 처음 배우고 있거나 기본 문법을 학습 중'),
(2, 'python_skill_level', 'intermediate', '기본 문법을 알고 있으며 일반적인 프로그래밍이 가능'),
(3, 'python_skill_level', 'advanced', '복잡한 프로젝트 개발이 가능하며 라이브러리 활용에 능숙'),
(4, 'python_skill_level', 'expert', '최적화, 아키텍처 설계, 고급 패턴 구현이 가능');

-- 코드 출력 구조 (ID: 5-8)
INSERT INTO setting_options (id, setting_type, option_value, description) VALUES
(5, 'code_output_structure', 'minimal', '핵심 로직만 간결하게 (주석 최소화)'),
(6, 'code_output_structure', 'standard', '일반적인 코드 구조 + 기본 주석'),
(7, 'code_output_structure', 'detailed', '자세한 주석 + 예외 처리 + 타입 힌트'),
(8, 'code_output_structure', 'comprehensive', '문서화 + 테스트 코드 + 최적화 제안');

-- 설명 스타일 (ID: 9-12)
INSERT INTO setting_options (id, setting_type, option_value, description) VALUES
(9, 'explanation_style', 'brief', '핵심 내용만 빠르게'),
(10, 'explanation_style', 'standard', '코드 + 간단한 설명'),
(11, 'explanation_style', 'detailed', '개념 + 이유 + 활용법'),
(12, 'explanation_style', 'educational', '단계별 + 예시 + 관련 개념');

-- 프로젝트 컨텍스트 (ID: 13-16)
INSERT INTO setting_options (id, setting_type, option_value, description) VALUES
(13, 'project_context', 'web_development', 'Django, Flask, FastAPI 등 웹 개발'),
(14, 'project_context', 'data_science', 'NumPy, Pandas, 머신러닝 등 데이터 사이언스'),
(15, 'project_context', 'automation', '스크립팅, 업무 자동화'),
(16, 'project_context', 'general_purpose', '다양한 목적의 범용 개발');

-- 주석 트리거 워크플로우 (ID: 17-20)
INSERT INTO setting_options (id, setting_type, option_value, description) VALUES
(17, 'comment_trigger_mode', 'immediate_insert', '생성된 코드를 커서 위치에 바로 삽입'),
(18, 'comment_trigger_mode', 'sidebar', '사이드바에 결과를 표시하고 검토 후 삽입'),
(19, 'comment_trigger_mode', 'confirm_insert', '코드를 미리보고 확인 대화상자에서 삽입 여부 선택'),
(20, 'comment_trigger_mode', 'inline_preview', '에디터에서 코드를 미리보고 키보드로 선택');

-- 선호 언어 기능 (ID: 21-24)
INSERT INTO setting_options (id, setting_type, option_value, description) VALUES
(21, 'preferred_language_feature', 'type_hints', '타입 힌트로 코드의 가독성과 안정성 향상'),
(22, 'preferred_language_feature', 'dataclasses', '데이터클래스로 간편한 클래스 정의'),
(23, 'preferred_language_feature', 'async_await', '비동기 프로그래밍으로 효율적인 I/O 처리'),
(24, 'preferred_language_feature', 'f_strings', 'f-strings로 깔끔한 문자열 포맷팅');

-- 에러 처리 선호도 (ID: 25-27)
INSERT INTO setting_options (id, setting_type, option_value, description) VALUES
(25, 'error_handling_preference', 'basic', '기본적인 try-except 구조'),
(26, 'error_handling_preference', 'detailed', '구체적인 예외 처리와 로깅'),
(27, 'error_handling_preference', 'robust', '완전한 에러 복구 메커니즘과 fallback');

-- ID 시퀀스 재설정
SELECT setval('setting_options_id_seq', 27, true);

-- 확인용 데이터 조회
SELECT 
    setting_type,
    COUNT(*) as option_count,
    string_agg(option_value, ', ' ORDER BY id) as options
FROM setting_options 
GROUP BY setting_type 
ORDER BY setting_type; 