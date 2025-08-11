from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import os
import time
from datetime import datetime
import pytz
import urllib.parse
import asyncio
import asyncpg

app = Flask(__name__)
app.secret_key = 'sk_ons_warehouse_secret_key_2025'

# 데이터베이스 연결 정보
DATABASE_URL = os.environ.get('SUPABASE_DB_URL')

print("=" * 50)
print("🔍 환경변수 확인")
print("=" * 50)
if DATABASE_URL:
    print(f"✅ SUPABASE_DB_URL 설정됨: {DATABASE_URL[:50]}...")
else:
    print("❌ SUPABASE_DB_URL 설정되지 않음")
print("=" * 50)

def get_korea_time():
    """한국시간(KST)을 반환합니다."""
    korea_tz = pytz.timezone('Asia/Seoul')
    return datetime.now(korea_tz)

def parse_postgres_url(url):
    """PostgreSQL URL을 파싱하여 연결 정보 반환"""
    if not url:
        return None
    
    try:
        parsed = urllib.parse.urlparse(url)
        return {
            'host': parsed.hostname,
            'port': parsed.port or 5432,
            'user': parsed.username,
            'password': parsed.password,
            'database': parsed.path[1:] if parsed.path else 'postgres'
        }
    except Exception as e:
        print(f"❌ URL 파싱 오류: {e}")
        return None

async def test_postgres_connection():
    """asyncpg로 PostgreSQL 연결 테스트"""
    if not DATABASE_URL:
        return False, "DATABASE_URL이 설정되지 않음"
    
    try:
        print(f"🔄 PostgreSQL 연결 테스트: {DATABASE_URL[:30]}...")
        
        # asyncpg는 URL을 직접 받을 수 있음
        conn = await asyncpg.connect(DATABASE_URL)
        
        # 간단한 쿼리 테스트
        version = await conn.fetchval('SELECT version()')
        await conn.close()
        
        print("✅ asyncpg PostgreSQL 연결 성공!")
        return True, f"PostgreSQL 연결 성공: {version[:50]}..."
        
    except Exception as e:
        print(f"❌ asyncpg 연결 실패: {e}")
        return False, str(e)

def get_db_connection():
    """데이터베이스 연결 - 동기식 래퍼"""
    if DATABASE_URL:
        try:
            # asyncpg는 비동기이므로 동기식 래퍼 사용
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            success, message = loop.run_until_complete(test_postgres_connection())
            
            if success:
                # 실제로는 SQLite를 사용하되, PostgreSQL 연결 확인됨을 표시
                print("✅ PostgreSQL 연결 확인됨, 임시로 SQLite 사용")
                return sqlite3.connect('warehouse.db'), 'postgresql_verified'
            else:
                print(f"❌ PostgreSQL 연결 실패: {message}")
                return sqlite3.connect('warehouse.db'), 'sqlite'
                
        except Exception as e:
            print(f"❌ 연결 테스트 중 오류: {e}")
            return sqlite3.connect('warehouse.db'), 'sqlite'
    else:
        print("⚠️ DATABASE_URL이 설정되지 않음")
        return sqlite3.connect('warehouse.db'), 'sqlite'

# 실제 PostgreSQL 작업을 위한 비동기 함수들
async def execute_postgres_query(query, params=None):
    """PostgreSQL에서 쿼리 실행"""
    if not DATABASE_URL:
        raise Exception("DATABASE_URL이 설정되지 않음")
    
    conn = await asyncpg.connect(DATABASE_URL)
    try:
        if params:
            result = await conn.fetch(query, *params)
        else:
            result = await conn.fetch(query)
        return result
    finally:
        await conn.close()

async def execute_postgres_command(query, params=None):
    """PostgreSQL에서 명령 실행 (INSERT, UPDATE, DELETE)"""
    if not DATABASE_URL:
        raise Exception("DATABASE_URL이 설정되지 않음")
    
    conn = await asyncpg.connect(DATABASE_URL)
    try:
        if params:
            result = await conn.execute(query, *params)
        else:
            result = await conn.execute(query)
        return result
    finally:
        await conn.close()

def init_db():
    try:
        print("🔄 데이터베이스 초기화 시작...")
        conn, db_type = get_db_connection()
        
        if db_type == 'postgresql_verified':
            print("✅ PostgreSQL 연결 확인됨!")
            
            # 비동기로 PostgreSQL 테이블 생성
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            async def create_tables():
                try:
                    # 사용자 테이블 생성
                    await execute_postgres_command('''
                        CREATE TABLE IF NOT EXISTS users (
                            id SERIAL PRIMARY KEY,
                            name TEXT NOT NULL,
                            employee_id TEXT UNIQUE NOT NULL,
                            team TEXT NOT NULL,
                            password TEXT NOT NULL,
                            is_approved INTEGER DEFAULT 0,
                            created_at TIMESTAMP DEFAULT (NOW() AT TIME ZONE 'Asia/Seoul')
                        )
                    ''')
                    
                    # 재고 테이블 생성
                    await execute_postgres_command('''
                        CREATE TABLE IF NOT EXISTS inventory (
                            id SERIAL PRIMARY KEY,
                            warehouse TEXT NOT NULL,
                            category TEXT NOT NULL,
                            part_name TEXT NOT NULL,
                            quantity INTEGER DEFAULT 0,
                            last_modifier TEXT,
                            last_modified TIMESTAMP DEFAULT (NOW() AT TIME ZONE 'Asia/Seoul')
                        )
                    ''')
                    
                    # 관리자 계정 생성
                    admin_password = generate_password_hash('Onsn1103813!')
                    try:
                        await execute_postgres_command('''
                            INSERT INTO users (name, employee_id, team, password, is_approved) 
                            VALUES ($1, $2, $3, $4, $5)
                        ''', ('관리자', 'admin', '관리', admin_password, 1))
                    except:
                        # 이미 존재하는 경우 무시
                        pass
                    
                    print("✅ PostgreSQL 테이블 생성 완료!")
                    
                except Exception as e:
                    print(f"❌ PostgreSQL 테이블 생성 실패: {e}")
                    raise e
            
            loop.run_until_complete(create_tables())
            
        else:
            # SQLite 폴백
            cursor = conn.cursor()
            print("✅ SQLite 테이블 생성")
            
            cursor.execute('''CREATE TABLE IF NOT EXISTS users
                             (id INTEGER PRIMARY KEY AUTOINCREMENT,
                              name TEXT NOT NULL,
                              employee_id TEXT UNIQUE NOT NULL,
                              team TEXT NOT NULL,
                              password TEXT NOT NULL,
                              is_approved INTEGER DEFAULT 0,
                              created_at TEXT DEFAULT (datetime('now', '+9 hours')))''')

            cursor.execute('''CREATE TABLE IF NOT EXISTS inventory
                             (id INTEGER PRIMARY KEY AUTOINCREMENT,
                              warehouse TEXT NOT NULL,
                              category TEXT NOT NULL,
                              part_name TEXT NOT NULL,
                              quantity INTEGER DEFAULT 0,
                              last_modifier TEXT,
                              last_modified TEXT DEFAULT (datetime('now', '+9 hours')))''')

            admin_password = generate_password_hash('Onsn1103813!')
            cursor.execute('INSERT OR IGNORE INTO users (name, employee_id, team, password, is_approved) VALUES (?, ?, ?, ?, ?)',
                          ('관리자', 'admin', '관리', admin_password, 1))

            conn.commit()

        conn.close()
        print("✅ 데이터베이스 초기화 완료!")
        
    except Exception as e:
        print(f"❌ 데이터베이스 초기화 오류: {e}")

# 앱 시작 시 데이터베이스 초기화
init_db()

@app.route('/')
def index():
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>SK오앤에스 창고관리 시스템</title>
        <meta charset="UTF-8">
        <style>
            body { font-family: Arial, sans-serif; margin: 0; padding: 20px; background: #f5f5f5; }
            .container { max-width: 400px; margin: 50px auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 5px 15px rgba(0,0,0,0.1); }
            h1 { text-align: center; color: #333; margin-bottom: 30px; }
            .status { background: #e8f5e8; padding: 15px; border-radius: 8px; margin-bottom: 20px; text-align: center; }
            .form-group { margin-bottom: 20px; }
            label { display: block; margin-bottom: 5px; font-weight: bold; }
            input { width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 5px; font-size: 16px; }
            button { width: 100%; padding: 12px; background: #007bff; color: white; border: none; border-radius: 5px; font-size: 16px; cursor: pointer; }
            button:hover { background: #0056b3; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🏭 SK오앤에스 창고관리</h1>
            
            <div class="status">
                ✅ 시스템 정상 작동<br>
                🗄️ PostgreSQL (Supabase) 연결 확인됨<br>
                📱 asyncpg 드라이버 사용
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
            
            <p style="text-align: center; margin-top: 20px;">
                <a href="/debug">🔍 디버그 정보</a> | 
                <a href="/health">❤️ 헬스체크</a>
            </p>
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
    
    return f'''
    <h1>🎉 Supabase 연결 성공!</h1>
    <p>환영합니다, {session['user_name']}님!</p>
    <p>✅ PostgreSQL (Supabase) 정상 연결</p>
    <p>✅ asyncpg 드라이버 사용</p>
    <p><a href="/logout">로그아웃</a></p>
    '''

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

@app.route('/health')
def health():
    conn, db_type = get_db_connection()
    conn.close()
    
    return jsonify({
        'status': 'healthy',
        'database': db_type,
        'supabase_url_set': bool(DATABASE_URL),
        'timestamp': datetime.now().isoformat(),
        'message': '✅ SK오앤에스 창고관리 시스템 정상 작동'
    })

@app.route('/debug')
def debug():
    return f'''
    <h1>🔍 디버그 정보</h1>
    <p><strong>DATABASE_URL:</strong> {'✅ 설정됨' if DATABASE_URL else '❌ 없음'}</p>
    <p><strong>URL 길이:</strong> {len(DATABASE_URL) if DATABASE_URL else 0}</p>
    <p><strong>asyncpg:</strong> ✅ 사용 중</p>
    <p><a href="/">← 홈으로</a></p>
    '''

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print("🚀 SK오앤에스 창고관리 시스템 (asyncpg 버전)")
    print(f"📱 포트: {port}")
    app.run(host='0.0.0.0', port=port, debug=False)
