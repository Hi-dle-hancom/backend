// MongoDB 초기화 스크립트
// HAPA History Service를 위한 데이터베이스 및 컬렉션 설정

print("🚀 HAPA MongoDB 초기화 시작...");

// hapa 데이터베이스로 전환
use('hapa');

// history 컬렉션 생성 (단일 컬렉션 설계)
db.createCollection('history', {
    validator: {
        $jsonSchema: {
            bsonType: "object",
            required: ["document_type", "user_id", "created_at"],
            properties: {
                document_type: {
                    bsonType: "string",
                    enum: ["session", "entry"],
                    description: "문서 타입 (session 또는 entry)"
                },
                user_id: {
                    bsonType: "int",
                    description: "사용자 ID"
                },
                created_at: {
                    bsonType: "date",
                    description: "생성 시간"
                },
                // 세션 전용 필드들
                session_id: {
                    bsonType: "string",
                    description: "세션 ID (세션 및 엔트리 모두에 있음)"
                },
                session_title: {
                    bsonType: "string",
                    description: "세션 제목 (세션 문서에만 있음)"
                },
                // 엔트리 전용 필드들
                entry_id: {
                    bsonType: "string",
                    description: "엔트리 ID (엔트리 문서에만 있음)"
                },
                content: {
                    bsonType: "string",
                    description: "대화 내용 (엔트리 문서에만 있음)"
                },
                conversation_type: {
                    bsonType: "string",
                    enum: ["question", "answer", "feedback", "error", "system"],
                    description: "대화 유형 (엔트리 문서에만 있음)"
                }
            }
        }
    }
});

print("✅ history 컬렉션 생성 완료");

// 기본 인덱스 생성
db.history.createIndex({ "document_type": 1 });
db.history.createIndex({ "user_id": 1 });
db.history.createIndex({ "session_id": 1 });
db.history.createIndex({ "created_at": -1 });

// 복합 인덱스 생성
db.history.createIndex({ 
    "document_type": 1, 
    "user_id": 1, 
    "created_at": -1 
});

// 세션 전용 인덱스 (고유 세션 ID)
db.history.createIndex({ 
    "document_type": 1, 
    "session_id": 1 
}, { 
    unique: true, 
    partialFilterExpression: { "document_type": "session" } 
});

// 엔트리 전용 인덱스 (고유 엔트리 ID)
db.history.createIndex({ 
    "entry_id": 1 
}, { 
    unique: true, 
    sparse: true 
});

// 텍스트 검색 인덱스 (content 필드)
db.history.createIndex({ 
    "content": "text" 
});

print("✅ 인덱스 생성 완료");

// 테스트 데이터 삽입 (개발용)
const testUserId = 1;
const testSessionId = "session_test_" + new Date().getTime();

// 테스트 세션 생성
db.history.insertOne({
    document_type: "session",
    session_id: testSessionId,
    user_id: testUserId,
    session_title: "테스트 세션",
    status: "active",
    primary_language: "python",
    tags: ["test", "mongodb"],
    project_name: "hapa-test",
    total_entries: 2,
    question_count: 1,
    answer_count: 1,
    created_at: new Date(),
    updated_at: new Date(),
    last_activity: new Date()
});

// 테스트 엔트리들 생성
db.history.insertMany([
    {
        document_type: "entry",
        entry_id: "entry_test_1",
        session_id: testSessionId,
        user_id: testUserId,
        conversation_type: "question",
        content: "Python에서 리스트를 정렬하는 방법을 알려주세요.",
        language: "python",
        code_snippet: null,
        file_name: null,
        line_number: null,
        response_time: 0.5,
        confidence_score: 0.95,
        created_at: new Date(Date.now() - 1000)
    },
    {
        document_type: "entry",
        entry_id: "entry_test_2",
        session_id: testSessionId,
        user_id: testUserId,
        conversation_type: "answer",
        content: "Python에서 리스트를 정렬하는 방법:\n\n1. sort() 메서드 사용 (원본 수정)\n2. sorted() 함수 사용 (새 리스트 반환)",
        language: "python",
        code_snippet: "# 원본 수정\nmy_list = [3, 1, 4, 1, 5]\nmy_list.sort()\nprint(my_list)  # [1, 1, 3, 4, 5]\n\n# 새 리스트 반환\nmy_list = [3, 1, 4, 1, 5]\nsorted_list = sorted(my_list)\nprint(sorted_list)  # [1, 1, 3, 4, 5]",
        file_name: null,
        line_number: null,
        response_time: 1.2,
        confidence_score: 0.98,
        created_at: new Date()
    }
]);

print("✅ 테스트 데이터 삽입 완료");

// 컬렉션 상태 확인
const sessionCount = db.history.countDocuments({ document_type: "session" });
const entryCount = db.history.countDocuments({ document_type: "entry" });

print(`📊 초기화 완료 통계:`);
print(`   - 총 세션 수: ${sessionCount}`);
print(`   - 총 엔트리 수: ${entryCount}`);
print(`   - 테스트 세션 ID: ${testSessionId}`);

print("🎉 HAPA MongoDB 초기화 완료!");