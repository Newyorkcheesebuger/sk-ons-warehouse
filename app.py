from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, Response
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import os
import urllib.parse
import uuid
from datetime import datetime, timedelta
import pytz
import sys
import csv
import io

app = Flask(__name__)
app.secret_key = 'sk_ons_warehouse_secret_key_2025'
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

# 세션 설정 강화
app.permanent_session_lifetime = timedelta(hours=8)
app.config['SESSION_COOKIE_SECURE'] = False
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_NAME'] = 'sk_ons_session'

# 업로드 폴더 생성
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# 환경변수 확인
DATABASE_URL = os.environ.get('SUPABASE_DB_URL')
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'Onsn1103813!')  # 기본값 유지

print("=" * 60)
print("🚀 SK오앤에스 창고관리 시스템 시작")
print("=" * 60)

# Supabase 연결 필수 체크
if not DATABASE_URL or not DATABASE_URL.startswith('postgresql://'):
    print("❌ 치명적 오류: 올바른 SUPABASE_DB_URL 환경변수가 설정되지 않았습니다!")
    print("📋 해결 방법:")
    print("   1. Render 대시보드에서 Environment Variables 설정")
    print("   2. SUPABASE_DB_URL 추가 (postgresql://로 시작해야 함)")
    print("   3. 재배포")
    print(f"   현재값: {DATABASE_URL[:30] if DATABASE_URL else 'None'}...")
    print("=" * 60)
    sys.exit(1)

print(f"✅ SUPABASE_DB_URL: {DATABASE_URL[:50]}...")

# 허용된 파일 확장자
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

# 올바른 창고 목록
WAREHOUSES = ['보라매창고', '관악창고', '양천창고', '강남창고', '강동창고']

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_korea_time():
    korea_tz = pytz.timezone('Asia/Seoul')
    return datetime.now(korea_tz)

def get_db_connection():
    """안정적인 데이터베이스 연결 함수"""
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
        
        conn.autocommit = False
        
        return conn
    except ImportError:
        print("❌ 치명적 오류: pg8000 라이브러리가 설치되지 않았습니다!")
        raise Exception("pg8000 라이브러리 필요")
    except Exception as e:
        print(f"❌ 치명적 오류: Supabase PostgreSQL 연결 실패!")
        print(f"   오류 내용: {e}")
        raise Exception(f"Supabase 연결 실패: {e}")

def init_db():
    """트랜잭션 오류 완전 해결된 초기화 함수"""
    conn = None
    try:
        print("🔄 Supabase PostgreSQL 연결 테스트 중...")
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT version()')
        version_info = cursor.fetchone()[0]
        print(f"✅ Supabase 연결 성공!")
        print(f"📊 PostgreSQL 버전: {version_info[:50]}...")
        
        print("🔄 데이터베이스 테이블 생성 중...")
        
        # 각 테이블을 개별 트랜잭션으로 생성
        tables_to_create = [
            ('users', '''CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                employee_id TEXT UNIQUE NOT NULL,
                team TEXT NOT NULL,
                password TEXT NOT NULL,
                is_approved INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT (NOW() AT TIME ZONE 'Asia/Seoul')
            )'''),
            ('inventory', '''CREATE TABLE IF NOT EXISTS inventory (
                id SERIAL PRIMARY KEY,
                warehouse TEXT NOT NULL,
                category TEXT NOT NULL,
                part_name TEXT NOT NULL,
                quantity INTEGER DEFAULT 0,
                last_modifier TEXT,
                last_modified TIMESTAMP DEFAULT (NOW() AT TIME ZONE 'Asia/Seoul')
            )'''),
            ('inventory_history', '''CREATE TABLE IF NOT EXISTS inventory_history (
                id SERIAL PRIMARY KEY,
                inventory_id INTEGER REFERENCES inventory(id),
                change_type TEXT,
                quantity_change INTEGER,
                modifier_name TEXT,
                modified_at TIMESTAMP DEFAULT (NOW() AT TIME ZONE 'Asia/Seoul')
            )'''),
            ('photos', '''CREATE TABLE IF NOT EXISTS photos (
                id SERIAL PRIMARY KEY,
                inventory_id INTEGER REFERENCES inventory(id),
                filename TEXT NOT NULL,
                original_name TEXT NOT NULL,
                file_size INTEGER,
                uploaded_by TEXT,
                uploaded_at TIMESTAMP DEFAULT (NOW() AT TIME ZONE 'Asia/Seoul')
            )''')
        ]
        
        for table_name, sql in tables_to_create:
            try:
                cursor.execute(sql)
                conn.commit()
                print(f"✅ {table_name} 테이블 처리 완료")
            except Exception as e:
                conn.rollback()
                print(f"⚠️ {table_name} 테이블 처리 중 오류 (무시): {e}")
                cursor.close()
                cursor = conn.cursor()
        
        # 관리자 계정 생성 (별도 트랜잭션)
        try:
            cursor.execute('SELECT id FROM users WHERE employee_id = %s', ('admin',))
            admin_exists = cursor.fetchone()
            
            if not admin_exists:
                admin_password_hash = generate_password_hash(ADMIN_PASSWORD)
                cursor.execute('''INSERT INTO users (name, employee_id, team, password, is_approved) 
                                 VALUES (%s, %s, %s, %s, %s)''',
                              ('관리자', 'admin', '관리', admin_password_hash, 1))
                conn.commit()
                print("✅ 관리자 계정 생성 완료")
            else:
                print("ℹ️ 관리자 계정 이미 존재")
                
        except Exception as admin_error:
            conn.rollback()
            print(f"⚠️ 관리자 계정 처리 중 오류: {admin_error}")
            
    except Exception as e:
        if conn:
            conn.rollback()
        print(f"❌ 초기화 중 오류: {e}")
        raise
    finally:
        if conn:
            conn.close()
        print("✅ 데이터베이스 초기화 완료!")

# 시스템 시작 시 Supabase 연결 필수 확인
print("🔍 Supabase 연결 상태 확인 중...")
init_db()
print("=" * 60)
print("✅ 시스템 준비 완료 - Supabase 연결됨")
print("=" * 60)

# ========
# 디버깅용 함수
# ========
def log_session_debug(route_name):
    """세션 디버깅 로그"""
    print(f"🔍 [{route_name}] 세션 상태:")
    print(f"   user_id: {session.get('user_id', 'None')}")
    print(f"   is_admin: {session.get('is_admin', 'None')}")
    print(f"   user_name: {session.get('user_name', 'None')}")
    print(f"   세션 키들: {list(session.keys())}")

# ========
# 라우트 정의 (강제 디버깅 버전)
# ========
@app.route('/')
def index():
    """메인 페이지 - 로그인된 사용자는 적절한 대시보드로 리다이렉트"""
    log_session_debug('/')
    
    if 'user_id' in session:
        if session.get('is_admin'):
            print("   → /admin/dashboard로 리디렉션")
            return redirect('/admin/dashboard')
        else:
            print("   → /dashboard로 리디렉션")
            return redirect('/dashboard')
    
    print("   → 로그인 페이지 표시")
    return render_template('login.html')

# ========
# 강제 세션 생성 라우트 (디버깅용)
# ========
@app.route('/force_admin_login')
def force_admin_login():
    """강제 관리자 로그인 (디버깅용)"""
    session.clear()
    session['user_id'] = 1
    session['user_name'] = '관리자'
    session['employee_id'] = 'admin'
    session['is_admin'] = True
    session.permanent = True
    
    print("🔧 강제 관리자 세션 생성 완료")
    log_session_debug('force_admin_login')
    
    return redirect('/admin/dashboard')

@app.route('/register', methods=['GET', 'POST'])
def register():
    """회원가입 페이지"""
    if request.method == 'POST':
        name = request.form['name']
        team = request.form['team']
        employee_number = request.form['employee_number']
        password = request.form['password']

        if len(password) < 8:
            flash('비밀번호는 8자리 이상이어야 합니다.')
            return render_template('register.html')

        if not employee_number.startswith('N'):
            employee_number = 'N' + employee_number
            
        if len(employee_number) != 8:
            flash('사번은 7자리 숫자여야 합니다.')
            return render_template('register.html')

        try:
            int(employee_number[1:])
        except ValueError:
            flash('사번 형식이 올바르지 않습니다.')
            return render_template('register.html')

        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute('SELECT id FROM users WHERE employee_id = %s', (employee_number,))
            if cursor.fetchone():
                flash('이미 등록된 사번입니다.')
                conn.close()
                return render_template('register.html')

            hashed_password = generate_password_hash(password)
            cursor.execute('INSERT INTO users (name, employee_id, team, password) VALUES (%s, %s, %s, %s)',
                          (name, employee_number, team, hashed_password))
            
            conn.commit()
            conn.close()
            flash('회원가입이 완료되었습니다. 관리자 승인 후 이용 가능합니다.')
            return redirect('/')
            
        except Exception as e:
            flash('회원가입 중 오류가 발생했습니다.')
            return render_template('register.html')

    return render_template('register.html')

@app.route('/login', methods=['POST'])
def login():
    """로그인 처리"""
    log_session_debug('login_start')
    
    try:
        employee_id = request.form.get('employee_id', '').strip()
        password = request.form.get('password', '').strip()

        print(f"🔍 로그인 시도: '{employee_id}'")

        if not employee_id or not password:
            flash('아이디와 비밀번호를 입력해주세요.')
            return redirect('/')

        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT id, name, employee_id, password, is_approved FROM users WHERE employee_id = %s', (employee_id,))
        user = cursor.fetchone()
        
        if user and check_password_hash(user[3], password):
            print(f"✅ 비밀번호 확인 성공: {user[1]}")
            
            if user[4] == 0:
                flash('관리자 승인 대기 중입니다.')
                conn.close()
                return redirect('/')

            # 세션 설정 강화
            session.clear()
            session['user_id'] = user[0]
            session['user_name'] = user[1]
            session['employee_id'] = user[2]
            session['is_admin'] = (employee_id == 'admin')
            session.permanent = True

            conn.close()

            print("✅ 세션 설정 완료:")
            log_session_debug('login_success')

            # 로그인 후 리다이렉트
            if session['is_admin']:
                print("🎯 관리자로 로그인 - /admin/dashboard로 이동")
                return redirect('/admin/dashboard')
            else:
                print("🎯 일반 사용자로 로그인 - /dashboard로 이동")
                return redirect('/dashboard')
        else:
            print("❌ 로그인 실패")
            flash('아이디 또는 비밀번호가 잘못되었습니다.')

        conn.close()
        return redirect('/')
            
    except Exception as e:
        print(f"❌ 로그인 처리 중 오류: {str(e)}")
        flash('로그인 중 오류가 발생했습니다. 다시 시도해주세요.')
        return redirect('/')

@app.route('/admin/dashboard')
def admin_dashboard():
    """관리자 전용 대시보드"""
    log_session_debug('/admin/dashboard')
    
    if 'user_id' not in session:
        print("   → 세션 없음, /로 리디렉션")
        flash('로그인이 필요합니다.')
        return redirect('/')

    if not session.get('is_admin'):
        print("   → 관리자 권한 없음, /dashboard로 리디렉션")
        flash('관리자 권한이 필요합니다.')
        return redirect('/dashboard')

    print("   → 관리자 대시보드 정상 표시")

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT id, name, employee_id, team, is_approved, created_at FROM users WHERE employee_id != %s ORDER BY created_at DESC', ('admin',))
        users = cursor.fetchall()
        
        # 재고 통계
        cursor.execute('SELECT COUNT(*) FROM inventory')
        total_items = cursor.fetchone()[0]
        
        cursor.execute('SELECT SUM(quantity) FROM inventory')
        total_quantity = cursor.fetchone()[0] or 0
        
        cursor.execute('SELECT warehouse, COUNT(*) FROM inventory GROUP BY warehouse')
        warehouse_stats = cursor.fetchall()
        
        conn.close()
        
        return render_template('admin_dashboard.html', 
                             users=users,
                             total_items=total_items,
                             total_quantity=total_quantity,
                             warehouse_stats=dict(warehouse_stats))
        
    except Exception as e:
        print(f"❌ 관리자 대시보드 오류: {str(e)}")
        flash(f'데이터를 불러오는 중 오류가 발생했습니다: {str(e)}')
        return redirect('/')

@app.route('/dashboard')
def user_dashboard():
    """사용자 대시보드"""
    log_session_debug('/dashboard')
    
    if 'user_id' not in session:
        print("   → 세션 없음, /로 리디렉션")
        return redirect('/')

    if session.get('is_admin'):
        print("   → 관리자 감지, /admin/dashboard로 리디렉션")
        return redirect('/admin/dashboard')

    print("   → 사용자 대시보드 정상 표시")
    return render_template('user_dashboard.html', warehouses=WAREHOUSES)

# 나머지 라우트들은 동일하게 유지...
@app.route('/logout')
def logout():
    """로그아웃"""
    session.clear()
    flash('로그아웃되었습니다.')
    return redirect('/')

# ========
# 에러 핸들러
# ========
@app.errorhandler(404)
def page_not_found(error):
    """404 에러 핸들러"""
    return '''
    <html>
    <head><title>404 - 페이지를 찾을 수 없음</title></head>
    <body style="font-family: Arial, sans-serif; text-align: center; padding: 50px;">
        <h1>404 - 페이지를 찾을 수 없습니다</h1>
        <p>요청하신 페이지가 존재하지 않습니다.</p>
        <a href="/" style="color: #007bff; text-decoration: none;">홈으로 돌아가기</a>
        <br><br>
        <a href="/force_admin_login" style="color: #dc3545; text-decoration: none;">[디버깅] 강제 관리자 로그인</a>
    </body>
    </html>
    ''', 404

# ========
# 메인 실행 부분
# ========
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    is_render = os.environ.get('RENDER') is not None
    
    print("")
    print("🎯 최종 시스템 정보:")
    print(f"📱 포트: {port}")
    print(f"🗄️ 데이터베이스: PostgreSQL (Supabase)")
    print(f"🔒 보안: 관리자/사용자 권한 분리")
    print(f"🌐 환경: {'Production (Render)' if is_render else 'Development'}")
    print(f"💾 데이터 보존: 영구 (Supabase)")
    print(f"📁 템플릿: 관리자/사용자 분리")
    print(f"🏪 창고: {', '.join(WAREHOUSES)}")
    print("=" * 60)
    print("🚀 SK오앤에스 창고관리 시스템 시작!")
    print("=" * 60)
    
    try:
        app.run(host='0.0.0.0', port=port, debug=not is_render)
    except Exception as e:
        print(f"❌ 서버 시작 실패: {e}")
        sys.exit(1)
