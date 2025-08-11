from flask import Flask, request, redirect, session, jsonify
import sqlite3
import os
import urllib.parse
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'sk_ons_warehouse_secret_key_2025'

# 환경변수 확인
DATABASE_URL = os.environ.get('SUPABASE_DB_URL')

print("=" * 50)
print("🔍 시스템 시작")
print("=" * 50)
if DATABASE_URL:
    print(f"✅ SUPABASE_DB_URL: {DATABASE_URL[:50]}...")
else:
    print("❌ SUPABASE_DB_URL 설정되지 않음")
print("=" * 50)

# pg8000 연결 테스트
def test_pg8000_connection():
    """pg8000으로 PostgreSQL 연결 테스트"""
    if not DATABASE_URL:
        return False, "DATABASE_URL이 설정되지 않음"
    
    try:
        import pg8000
        
        # URL 파싱
        parsed = urllib.parse.urlparse(DATABASE_URL)
        
        print(f"🔍 연결 정보:")
        print(f"   Host: {parsed.hostname}")
        print(f"   Port: {parsed.port}")
        print(f"   User: {parsed.username}")
        print(f"   Database: {parsed.path[1:] if parsed.path else 'postgres'}")
        
        # pg8000 연결 (개별 파라미터 사용)
        conn = pg8000.connect(
            host=parsed.hostname,
            port=parsed.port or 5432,
            user=parsed.username,
            password=parsed.password,
            database=parsed.path[1:] if parsed.path else 'postgres'
        )
        
        # 간단한 쿼리 테스트
        cursor = conn.cursor()
        cursor.execute("SELECT version()")
        result = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        print("✅ pg8000 연결 성공!")
        return True, f"PostgreSQL 연결 성공: {result[0][:50]}..."
        
    except ImportError:
        print("❌ pg8000 라이브러리 없음")
        return False, "pg8000 라이브러리 설치 필요"
    except Exception as e:
        print(f"❌ PostgreSQL 연결 실패: {e}")
        return False, str(e)

# SQLite 초기화
def init_sqlite():
    """SQLite 데이터베이스 초기화"""
    try:
        conn = sqlite3.connect('warehouse.db')
        c = conn.cursor()

        # 사용자 테이블
        c.execute('''CREATE TABLE IF NOT EXISTS users
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      name TEXT NOT NULL,
                      employee_id TEXT UNIQUE NOT NULL,
                      team TEXT NOT NULL,
                      password TEXT NOT NULL,
                      is_approved INTEGER DEFAULT 0,
                      created_at TEXT DEFAULT (datetime('now', '+9 hours')))''')

        # 관리자 계정 생성
        admin_password = generate_password_hash('Onsn1103813!')
        c.execute('INSERT OR IGNORE INTO users (name, employee_id, team, password, is_approved) VALUES (?, ?, ?, ?, ?)',
                  ('관리자', 'admin', '관리', admin_password, 1))

        conn.commit()
        conn.close()
        print("✅ SQLite 초기화 완료")
        return True
        
    except Exception as e:
        print(f"❌ SQLite 초기화 실패: {e}")
        return False

# PostgreSQL 테이블 생성
def create_postgres_tables():
    """PostgreSQL에 테이블 생성"""
    if not DATABASE_URL:
        return False
    
    try:
        import pg8000
        
        parsed = urllib.parse.urlparse(DATABASE_URL)
        
        conn = pg8000.connect(
            host=parsed.hostname,
            port=parsed.port or 5432,
            user=parsed.username,
            password=parsed.password,
            database=parsed.path[1:] if parsed.path else 'postgres'
        )
        
        cursor = conn.cursor()
        
        # 사용자 테이블 생성
        cursor.execute('''CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            employee_id TEXT UNIQUE NOT NULL,
            team TEXT NOT NULL,
            password TEXT NOT NULL,
            is_approved INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT (NOW() AT TIME ZONE 'Asia/Seoul')
        )''')
        
        # 관리자 계정 생성
        admin_password = generate_password_hash('Onsn1103813!')
        try:
            cursor.execute("INSERT INTO users (name, employee_id, team, password, is_approved) VALUES (%s, %s, %s, %s, %s)",
                          ('관리자', 'admin', '관리', admin_password, 1))
        except:
            # 이미 존재하는 경우 무시
            pass
        
        conn.commit()
        cursor.close()
        conn.close()
        print("✅ PostgreSQL 테이블 생성 완료")
        return True
        
    except Exception as e:
        print(f"❌ PostgreSQL 테이블 생성 실패: {e}")
        return False

# 시스템 초기화
print("🔄 시스템 초기화 중...")

# PostgreSQL 연결 테스트
postgres_success, postgres_message = test_pg8000_connection()
if postgres_success:
    print("✅ PostgreSQL 사용 가능")
    postgres_tables_created = create_postgres_tables()
else:
    print(f"❌ PostgreSQL 사용 불가: {postgres_message}")
    postgres_tables_created = False

# SQLite 초기화 (항상 백업용)
sqlite_success = init_sqlite()

print("🎯 초기화 완료!")

@app.route('/')
def index():
    postgres_status = "✅ 연결됨" if postgres_success else "❌ 연결 실패"
    sqlite_status = "✅ 사용 가능" if sqlite_success else "❌ 사용 불가"
    
    return f'''
    <!DOCTYPE html>
    <html>
    <head>
        <title>SK오앤에스 창고관리 시스템</title>
        <meta charset="UTF-8">
        <style>
            body {{ font-family: Arial, sans-serif; margin: 0; padding: 20px; background: #f5f5f5; }}
            .container {{ max-width: 500px; margin: 50px auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 5px 15px rgba(0,0,0,0.1); }}
            h1 {{ text-align: center; color: #333; margin-bottom: 30px; }}
            .status {{ background: {'#e8f5e8' if postgres_success else '#fff3cd'}; padding: 15px; border-radius: 8px; margin-bottom: 20px; }}
            .form-group {{ margin-bottom: 20px; }}
            label {{ display: block; margin-bottom: 5px; font-weight: bold; }}
            input {{ width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 5px; font-size: 16px; }}
            button {{ width: 100%; padding: 12px; background: #007bff; color: white; border: none; border-radius: 5px; font-size: 16px; cursor: pointer; }}
            button:hover {{ background: #0056b3; }}
            .links {{ text-align: center; margin-top: 20px; }}
            .links a {{ margin: 0 10px; color: #007bff; text-decoration: none; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🏭 SK오앤에스 창고관리</h1>
            
            <div class="status">
                <h3>📊 시스템 상태</h3>
                <p><strong>PostgreSQL (Supabase):</strong> {postgres_status}</p>
                <p><strong>SQLite (백업):</strong> {sqlite_status}</p>
                <p><strong>pg8000:</strong> ✅ 순수 Python 드라이버</p>
                {f'<p><strong>✅ 데이터 영구 보존:</strong> 가능</p>' if postgres_success else '<p><strong>⚠️ 데이터 보존:</strong> SQLite 임시 사용</p>'}
                {f'<p style="font-size: 12px; color: #666;"><strong>상세:</strong> {postgres_message}</p>' if postgres_success else ''}
            </div>
            
            <form method="POST" action="/login">
                <div class="form-group">
                    <label for="employee_id">사번</label>
                    <input type="text" id="employee_id" name="employee_id" placeholder="admin" required>
                </div>
                
                <div class="form-group">
                    <label for="password">비밀번호</label>
                    <input type="password" id="password" name="password" placeholder="Onsn1103813!" required>
                </div>
                
                <button type="submit">로그인</button>
            </form>
            
            <div class="links">
                <a href="/health">❤️ 헬스체크</a>
                <a href="/debug">🔍 디버그</a>
            </div>
        </div>
    </body>
    </html>
    '''

@app.route('/login', methods=['POST'])
def login():
    employee_id = request.form.get('employee_id', '')
    password = request.form.get('password', '')

    if employee_id == 'admin' and password == 'Onsn1103813!':
        session.clear()
        session['user_id'] = 1
        session['user_name'] = '관리자'
        session['employee_id'] = 'admin'
        session['is_admin'] = True
        session.permanent = True
        return redirect('/dashboard')
    else:
        return redirect('/')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect('/')
    
    db_status = "PostgreSQL (Supabase)" if postgres_success else "SQLite (임시)"
    data_preservation = "영구 보존" if postgres_success else "재배포 시 초기화"
    
    return f'''
    <!DOCTYPE html>
    <html>
    <head>
        <title>관리자 대시보드</title>
        <meta charset="UTF-8">
        <style>
            body {{ font-family: Arial, sans-serif; margin: 0; padding: 20px; background: #f5f5f5; }}
            .container {{ max-width: 600px; margin: 50px auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 5px 15px rgba(0,0,0,0.1); }}
            h1 {{ text-align: center; color: #333; margin-bottom: 30px; }}
            .success {{ background: #e8f5e8; padding: 20px; border-radius: 8px; margin-bottom: 20px; }}
            .info {{ background: #e3f2fd; padding: 15px; border-radius: 8px; margin-bottom: 20px; }}
            .logout {{ text-align: center; margin-top: 30px; }}
            .logout a {{ padding: 10px 20px; background: #dc3545; color: white; text-decoration: none; border-radius: 5px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🎉 로그인 성공!</h1>
            
            <div class="success">
                <h3>환영합니다, {session['user_name']}님!</h3>
                <p>✅ 관리자 권한으로 로그인되었습니다.</p>
            </div>
            
            <div class="info">
                <h3>📊 시스템 정보</h3>
                <p><strong>데이터베이스:</strong> {db_status}</p>
                <p><strong>데이터 보존:</strong> {data_preservation}</p>
                <p><strong>드라이버:</strong> pg8000 (순수 Python)</p>
                <p><strong>상태:</strong> {'🟢 정상 작동' if postgres_success else '🟡 SQLite 폴백'}</p>
                {f'<p><strong>Supabase:</strong> 연결 성공 ✅</p>' if postgres_success else '<p><strong>Supabase:</strong> 연결 실패, SQLite 사용 중 ⚠️</p>'}
            </div>
            
            <div class="logout">
                <a href="/logout">로그아웃</a>
            </div>
        </div>
    </body>
    </html>
    '''

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

@app.route('/health')
def health():
    return jsonify({
        'status': 'healthy',
        'postgresql': postgres_success,
        'sqlite': sqlite_success,
        'database_url_set': bool(DATABASE_URL),
        'timestamp': datetime.now().isoformat(),
        'message': f'✅ 시스템 정상 작동 ({("PostgreSQL" if postgres_success else "SQLite")})'
    })

@app.route('/debug')
def debug():
    return f'''
    <h1>🔍 디버그 정보</h1>
    <p><strong>DATABASE_URL:</strong> {'✅ 설정됨' if DATABASE_URL else '❌ 없음'}</p>
    <p><strong>PostgreSQL:</strong> {'✅ 연결됨' if postgres_success else '❌ 연결 실패'}</p>
    <p><strong>SQLite:</strong> {'✅ 사용 가능' if sqlite_success else '❌ 사용 불가'}</p>
    <p><strong>pg8000:</strong> ✅ 순수 Python 드라이버</p>
    <p><strong>메시지:</strong> {postgres_message if postgres_success else '연결 실패'}</p>
    <p><a href="/">← 홈으로</a></p>
    '''

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print("🚀 SK오앤에스 창고관리 시스템 시작")
    print(f"📱 포트: {port}")
    print(f"🗄️ 데이터베이스: {'PostgreSQL (Supabase)' if postgres_success else 'SQLite (폴백)'}")
    print(f"💾 데이터 보존: {'영구' if postgres_success else '임시'}")
    app.run(host='0.0.0.0', port=port, debug=False)
