#!/usr/bin/env python3
"""
PostgreSQL에서 MongoDB로 히스토리 데이터 마이그레이션 스크립트
HAPA 프로젝트용

사용법:
    python migrate_to_mongodb.py
"""

import asyncio
import json
import logging
import os
from datetime import datetime
from typing import Dict, List, Any

import asyncpg
from motor.motor_asyncio import AsyncIOMotorClient

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

class DataMigrator:
    """PostgreSQL에서 MongoDB로 데이터 마이그레이션"""
    
    def __init__(self):
        # PostgreSQL 설정
        self.pg_url = os.getenv("DATABASE_URL", "postgresql://devk1212gh:1212@localhost:5432/hidle")
        
        # MongoDB 설정
        self.mongo_url = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
        self.mongo_db = "hapa"
        self.mongo_collection = "history"
        
        # 연결 인스턴스
        self.pg_conn = None
        self.mongo_client = None
        self.mongo_db_instance = None
        self.mongo_collection_instance = None
        
        logger.info(f"🔧 PostgreSQL URL: {self.pg_url}")
        logger.info(f"🔧 MongoDB URL: {self.mongo_url}")
    
    async def connect_databases(self):
        """데이터베이스 연결"""
        try:
            # PostgreSQL 연결
            logger.info("🔌 PostgreSQL 연결 시도...")
            self.pg_conn = await asyncpg.connect(self.pg_url)
            logger.info("✅ PostgreSQL 연결 성공")
            
            # MongoDB 연결
            logger.info("🔌 MongoDB 연결 시도...")
            self.mongo_client = AsyncIOMotorClient(self.mongo_url)
            self.mongo_db_instance = self.mongo_client[self.mongo_db]
            self.mongo_collection_instance = self.mongo_db_instance[self.mongo_collection]
            
            # MongoDB 연결 테스트
            await self.mongo_client.admin.command('ping')
            logger.info("✅ MongoDB 연결 성공")
            
        except Exception as e:
            logger.error(f"❌ 데이터베이스 연결 실패: {e}")
            raise
    
    async def check_postgresql_tables(self):
        """PostgreSQL 테이블 확인"""
        try:
            # 테이블 존재 확인
            tables_query = """
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name IN ('conversation_sessions', 'conversation_entries', 'history_sessions', 'history_entries')
            """
            
            tables = await self.pg_conn.fetch(tables_query)
            existing_tables = [row['table_name'] for row in tables]
            
            logger.info(f"🔍 PostgreSQL 히스토리 관련 테이블: {existing_tables}")
            
            if not existing_tables:
                logger.warning("⚠️ PostgreSQL에 히스토리 테이블이 없습니다. 샘플 데이터 생성 모드로 진행합니다.")
                return False
            
            # 각 테이블의 레코드 수 확인
            for table in existing_tables:
                count_query = f"SELECT COUNT(*) FROM {table}"
                count = await self.pg_conn.fetchval(count_query)
                logger.info(f"📊 테이블 {table}: {count}개 레코드")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ PostgreSQL 테이블 확인 실패: {e}")
            return False
    
    async def migrate_sessions(self):
        """세션 데이터 마이그레이션"""
        try:
            # PostgreSQL에서 세션 데이터 조회 시도
            session_queries = [
                "SELECT * FROM conversation_sessions ORDER BY created_at DESC",
                "SELECT * FROM history_sessions ORDER BY created_at DESC",
                "SELECT * FROM sessions ORDER BY created_at DESC"
            ]
            
            sessions_data = []
            for query in session_queries:
                try:
                    sessions = await self.pg_conn.fetch(query)
                    if sessions:
                        sessions_data = sessions
                        logger.info(f"✅ PostgreSQL 세션 데이터 발견: {len(sessions)}개")
                        break
                except Exception:
                    continue
            
            if not sessions_data:
                logger.warning("⚠️ PostgreSQL에서 세션 데이터를 찾을 수 없습니다. 샘플 데이터 생성")
                return await self.create_sample_data()
            
            # MongoDB로 마이그레이션
            migrated_count = 0
            for session in sessions_data:
                try:
                    # PostgreSQL 세션을 MongoDB 문서로 변환
                    mongo_session = {
                        "document_type": "session",
                        "session_id": session.get('session_id', f"migrated_{session.get('id', 'unknown')}"),
                        "user_id": session.get('user_id', 1),
                        "session_title": session.get('session_title', session.get('title', 'Migrated Session')),
                        "status": session.get('status', 'active'),
                        "primary_language": session.get('primary_language', 'python'),
                        "tags": session.get('tags', []),
                        "project_name": session.get('project_name', 'migrated'),
                        "total_entries": session.get('total_entries', 0),
                        "question_count": session.get('question_count', 0),
                        "answer_count": session.get('answer_count', 0),
                        "created_at": session.get('created_at', datetime.now()),
                        "updated_at": session.get('updated_at', datetime.now()),
                        "last_activity": session.get('last_activity', datetime.now()),
                        "_migrated_from": "postgresql",
                        "_migrated_at": datetime.now()
                    }
                    
                    # MongoDB에 삽입 (중복 방지)
                    await self.mongo_collection_instance.update_one(
                        {
                            "document_type": "session",
                            "session_id": mongo_session["session_id"],
                            "user_id": mongo_session["user_id"]
                        },
                        {"$set": mongo_session},
                        upsert=True
                    )
                    
                    migrated_count += 1
                    
                except Exception as e:
                    logger.error(f"❌ 세션 마이그레이션 실패: {e}")
                    continue
            
            logger.info(f"✅ 세션 마이그레이션 완료: {migrated_count}개")
            return migrated_count
            
        except Exception as e:
            logger.error(f"❌ 세션 마이그레이션 실패: {e}")
            return 0
    
    async def migrate_entries(self):
        """엔트리 데이터 마이그레이션"""
        try:
            # PostgreSQL에서 엔트리 데이터 조회 시도
            entry_queries = [
                "SELECT * FROM conversation_entries ORDER BY created_at DESC",
                "SELECT * FROM history_entries ORDER BY created_at DESC",
                "SELECT * FROM entries ORDER BY created_at DESC"
            ]
            
            entries_data = []
            for query in entry_queries:
                try:
                    entries = await self.pg_conn.fetch(query)
                    if entries:
                        entries_data = entries
                        logger.info(f"✅ PostgreSQL 엔트리 데이터 발견: {len(entries)}개")
                        break
                except Exception:
                    continue
            
            if not entries_data:
                logger.warning("⚠️ PostgreSQL에서 엔트리 데이터를 찾을 수 없습니다.")
                return 0
            
            # MongoDB로 마이그레이션
            migrated_count = 0
            for entry in entries_data:
                try:
                    # PostgreSQL 엔트리를 MongoDB 문서로 변환
                    mongo_entry = {
                        "document_type": "entry",
                        "entry_id": entry.get('entry_id', f"migrated_{entry.get('id', 'unknown')}"),
                        "session_id": entry.get('session_id', 'migrated_session'),
                        "user_id": entry.get('user_id', 1),
                        "conversation_type": entry.get('conversation_type', entry.get('type', 'question')),
                        "content": entry.get('content', ''),
                        "language": entry.get('language', 'python'),
                        "code_snippet": entry.get('code_snippet'),
                        "file_name": entry.get('file_name'),
                        "line_number": entry.get('line_number'),
                        "response_time": entry.get('response_time', 0.0),
                        "confidence_score": entry.get('confidence_score', 0.0),
                        "created_at": entry.get('created_at', datetime.now()),
                        "_migrated_from": "postgresql",
                        "_migrated_at": datetime.now()
                    }
                    
                    # MongoDB에 삽입 (중복 방지)
                    await self.mongo_collection_instance.update_one(
                        {
                            "document_type": "entry",
                            "entry_id": mongo_entry["entry_id"],
                            "user_id": mongo_entry["user_id"]
                        },
                        {"$set": mongo_entry},
                        upsert=True
                    )
                    
                    migrated_count += 1
                    
                except Exception as e:
                    logger.error(f"❌ 엔트리 마이그레이션 실패: {e}")
                    continue
            
            logger.info(f"✅ 엔트리 마이그레이션 완료: {migrated_count}개")
            return migrated_count
            
        except Exception as e:
            logger.error(f"❌ 엔트리 마이그레이션 실패: {e}")
            return 0
    
    async def create_sample_data(self):
        """샘플 데이터 생성 (PostgreSQL에 데이터가 없을 때)"""
        try:
            logger.info("🔧 샘플 데이터 생성 시작...")
            
            # 샘플 세션 생성
            sample_sessions = [
                {
                    "document_type": "session",
                    "session_id": "sample_session_1",
                    "user_id": 1,
                    "session_title": "Python 기초 학습",
                    "status": "active",
                    "primary_language": "python",
                    "tags": ["python", "기초", "학습"],
                    "project_name": "파이썬 프로젝트",
                    "total_entries": 4,
                    "question_count": 2,
                    "answer_count": 2,
                    "created_at": datetime.now(),
                    "updated_at": datetime.now(),
                    "last_activity": datetime.now()
                },
                {
                    "document_type": "session",
                    "session_id": "sample_session_2",
                    "user_id": 1,
                    "session_title": "데이터 분석 세션",
                    "status": "active",
                    "primary_language": "python",
                    "tags": ["데이터분석", "pandas", "numpy"],
                    "project_name": "데이터 분석 프로젝트",
                    "total_entries": 6,
                    "question_count": 3,
                    "answer_count": 3,
                    "created_at": datetime.now(),
                    "updated_at": datetime.now(),
                    "last_activity": datetime.now()
                }
            ]
            
            # 샘플 엔트리 생성
            sample_entries = [
                {
                    "document_type": "entry",
                    "entry_id": "sample_entry_1",
                    "session_id": "sample_session_1",
                    "user_id": 1,
                    "conversation_type": "question",
                    "content": "Python에서 리스트와 튜플의 차이점은 무엇인가요?",
                    "language": "python",
                    "code_snippet": None,
                    "file_name": None,
                    "line_number": None,
                    "response_time": 0.5,
                    "confidence_score": 0.95,
                    "created_at": datetime.now()
                },
                {
                    "document_type": "entry",
                    "entry_id": "sample_entry_2",
                    "session_id": "sample_session_1",
                    "user_id": 1,
                    "conversation_type": "answer",
                    "content": "리스트는 가변(mutable)이고 튜플은 불변(immutable)입니다. 리스트는 []로, 튜플은 ()로 표현합니다.",
                    "language": "python",
                    "code_snippet": "# 리스트 (가변)\nmy_list = [1, 2, 3]\nmy_list.append(4)\nprint(my_list)  # [1, 2, 3, 4]\n\n# 튜플 (불변)\nmy_tuple = (1, 2, 3)\n# my_tuple.append(4)  # 오류 발생!",
                    "file_name": None,
                    "line_number": None,
                    "response_time": 1.2,
                    "confidence_score": 0.98,
                    "created_at": datetime.now()
                },
                {
                    "document_type": "entry",
                    "entry_id": "sample_entry_3",
                    "session_id": "sample_session_2",
                    "user_id": 1,
                    "conversation_type": "question",
                    "content": "pandas DataFrame에서 특정 열의 값을 기준으로 정렬하는 방법을 알려주세요.",
                    "language": "python",
                    "code_snippet": None,
                    "file_name": None,
                    "line_number": None,
                    "response_time": 0.3,
                    "confidence_score": 0.92,
                    "created_at": datetime.now()
                },
                {
                    "document_type": "entry",
                    "entry_id": "sample_entry_4",
                    "session_id": "sample_session_2",
                    "user_id": 1,
                    "conversation_type": "answer",
                    "content": "pandas DataFrame에서 정렬을 위해 sort_values() 메서드를 사용합니다.",
                    "language": "python",
                    "code_snippet": "import pandas as pd\n\n# 샘플 DataFrame 생성\ndf = pd.DataFrame({\n    'name': ['Alice', 'Bob', 'Charlie'],\n    'age': [25, 30, 35],\n    'score': [85, 90, 88]\n})\n\n# age 열을 기준으로 오름차순 정렬\ndf_sorted = df.sort_values('age')\nprint(df_sorted)\n\n# score 열을 기준으로 내림차순 정렬\ndf_sorted_desc = df.sort_values('score', ascending=False)\nprint(df_sorted_desc)",
                    "file_name": None,
                    "line_number": None,
                    "response_time": 1.5,
                    "confidence_score": 0.96,
                    "created_at": datetime.now()
                }
            ]
            
            # MongoDB에 샘플 데이터 삽입
            await self.mongo_collection_instance.insert_many(sample_sessions)
            await self.mongo_collection_instance.insert_many(sample_entries)
            
            logger.info(f"✅ 샘플 데이터 생성 완료: {len(sample_sessions)}개 세션, {len(sample_entries)}개 엔트리")
            return len(sample_sessions)
            
        except Exception as e:
            logger.error(f"❌ 샘플 데이터 생성 실패: {e}")
            return 0
    
    async def verify_migration(self):
        """마이그레이션 검증"""
        try:
            # MongoDB 데이터 확인
            session_count = await self.mongo_collection_instance.count_documents({"document_type": "session"})
            entry_count = await self.mongo_collection_instance.count_documents({"document_type": "entry"})
            
            logger.info(f"📊 마이그레이션 결과:")
            logger.info(f"   - 총 세션 수: {session_count}")
            logger.info(f"   - 총 엔트리 수: {entry_count}")
            
            # 샘플 데이터 조회
            sample_sessions = await self.mongo_collection_instance.find(
                {"document_type": "session"}
            ).limit(3).to_list(3)
            
            sample_entries = await self.mongo_collection_instance.find(
                {"document_type": "entry"}
            ).limit(3).to_list(3)
            
            logger.info(f"📋 샘플 세션 데이터:")
            for session in sample_sessions:
                logger.info(f"   - {session['session_id']}: {session['session_title']}")
            
            logger.info(f"📋 샘플 엔트리 데이터:")
            for entry in sample_entries:
                logger.info(f"   - {entry['entry_id']}: {entry['content'][:50]}...")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ 마이그레이션 검증 실패: {e}")
            return False
    
    async def close_connections(self):
        """연결 종료"""
        try:
            if self.pg_conn:
                await self.pg_conn.close()
                logger.info("✅ PostgreSQL 연결 종료")
            
            if self.mongo_client:
                self.mongo_client.close()
                logger.info("✅ MongoDB 연결 종료")
                
        except Exception as e:
            logger.error(f"❌ 연결 종료 실패: {e}")

    async def run_migration(self):
        """전체 마이그레이션 실행"""
        try:
            logger.info("🚀 MongoDB 마이그레이션 시작")
            
            # 1. 데이터베이스 연결
            await self.connect_databases()
            
            # 2. PostgreSQL 테이블 확인
            has_pg_tables = await self.check_postgresql_tables()
            
            # 3. 데이터 마이그레이션
            if has_pg_tables:
                sessions_migrated = await self.migrate_sessions()
                entries_migrated = await self.migrate_entries()
                logger.info(f"✅ PostgreSQL 마이그레이션 완료: {sessions_migrated}개 세션, {entries_migrated}개 엔트리")
            else:
                # PostgreSQL에 데이터가 없으면 샘플 데이터 생성
                await self.create_sample_data()
            
            # 4. 마이그레이션 검증
            await self.verify_migration()
            
            logger.info("🎉 MongoDB 마이그레이션 완료!")
            
        except Exception as e:
            logger.error(f"❌ 마이그레이션 실패: {e}")
            raise
        finally:
            await self.close_connections()

async def main():
    """메인 함수"""
    try:
        migrator = DataMigrator()
        await migrator.run_migration()
    except KeyboardInterrupt:
        logger.info("🛑 사용자에 의해 중단됨")
    except Exception as e:
        logger.error(f"💥 마이그레이션 실패: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)