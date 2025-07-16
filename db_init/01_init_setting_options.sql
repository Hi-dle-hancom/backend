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

-- 🐍 Python 스킬 레벨 (2가지)
INSERT INTO setting_options (id, setting_type, option_value, description) VALUES
(1, 'python_skill_level', 'beginner', '기본 문법 학습 중'),
(2, 'python_skill_level', 'intermediate', '일반적 프로그래밍 가능');

-- 📝 코드 출력 구조 (3가지)
INSERT INTO setting_options (id, setting_type, option_value, description) VALUES
(3, 'code_output_structure', 'minimal', '핵심 로직만 간결하게'),
(4, 'code_output_structure', 'standard', '기본 주석 포함'),
(5, 'code_output_structure', 'detailed', '예외처리 + 타입힌트');

-- 💬 설명 스타일 (4가지)
INSERT INTO setting_options (id, setting_type, option_value, description) VALUES
(6, 'explanation_style', 'brief', '핵심 내용만'),
(7, 'explanation_style', 'standard', '코드 + 간단 설명'),
(8, 'explanation_style', 'detailed', '개념 + 이유 + 활용법'),
(9, 'explanation_style', 'educational', '단계별 + 예시');

-- ID 시퀀스 재설정
SELECT setval('setting_options_id_seq', 9, true);

-- 확인용 데이터 조회
SELECT 
    setting_type,
    COUNT(*) as option_count,
    string_agg(option_value, ', ' ORDER BY id) as options
FROM setting_options 
GROUP BY setting_type 
ORDER BY setting_type; 