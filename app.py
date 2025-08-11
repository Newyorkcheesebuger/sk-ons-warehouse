from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import os
import time
from datetime import datetime
import pytz

# PostgreSQL 지원 추가 (pg8000 사용)
PG_AVAILABLE = False
try:
    import pg8000.native
    PG_AVAILABLE = True
    print("✅ pg8000 라이브러리 로드 성공")
except ImportError as e:
    print(f"⚠️ pg8000 라이브러리 로드 실패: {e}")
    print("🔄 SQLite 모드로 실행됩니다")

app = Flask(__name__)
app.secret_key = 'sk_ons_warehouse_secret_key_2025'

# 데이터베이스 연결 정보
DATABASE_URL = os.environ.get('SUPABASE_DB_URL')

def get_db_connection():
    """데이터베이스 연결 - Supabase 우선, 없으면 SQLite"""
    if DATABASE_URL and PG_AVAILABLE:
        try:
            print(f"🔄 Supabase 연결 시도: {DATABASE_URL[:30]}...")
            conn = pg8000.native.Connection(DATABASE_URL)
            print("✅ Supabase PostgreSQL 연결 성공!")
            return conn, 'postgresql'
        except Exception as e:
            print(f"❌ Supabase 연결 실패: {e}")
            print("🔄 SQLite로 폴백...")
            return sqlite3.connect('warehouse.db'), 'sqlite'
    else:
        if not DATABASE_URL:
            print("⚠️ SUPABASE_DB_URL 환경변수가 설정되지 않음")
        if not PG_AVAILABLE:
            print("⚠️ pg8000 라이브러리가 설치되지 않음")
        print("🔄 SQLite 사용")
        return sqlite3.connect('warehouse.db'), 'sqlite'

def get_korea_time():
    """한국시간(KST)을 반환합니다."""
    korea_tz = pytz.timezone('Asia/Seoul')
    return datetime.now(korea_tz)

def init_db():
    try:
        print("🔄 데이터베이스 초기화 시작...")
        conn, db_type = get_db_connection()
        
        if db_type == 'postgresql':
            cursor = conn.cursor()
            print("✅ PostgreSQL (Supabase) 테이블 생성")
            
            # PostgreSQL용 테이블 생성
            cursor.execute('''CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                employee_id TEXT UNIQUE NOT NULL,
                team TEXT NOT NULL,
                password TEXT NOT NULL,
                is_approved INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT (NOW() AT TIME ZONE 'Asia/Seoul')
            )''')

            cursor.execute('''CREATE TABLE IF NOT EXISTS inventory (
                id SERIAL PRIMARY KEY,
                warehouse TEXT NOT NULL,
                category TEXT NOT NULL,
                part_name TEXT NOT NULL,
                quantity INTEGER DEFAULT 0,
                last_modifier TEXT,
                last_modified TIMESTAMP DEFAULT (NOW() AT TIME ZONE 'Asia/Seoul')
            )''')

            # 관리자 계정 생성 (PostgreSQL)
            admin_password = generate_password_hash('Onsn1103813!')
            cursor.execute('''INSERT INTO users (name, employee_id, team, password, is_approved) 
                             VALUES (%s, %s, %s, %s, %s) ON CONFLICT (employee_id) DO NOTHING''',
                          ('관리자', 'admin', '관리', admin_password, 1))
            
        else:
            cursor = conn.cursor()
            print("✅ SQLite 테이블 생성")
            
            # SQLite용 테이블 생성
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

            # 관리자 계정 생성 (SQLite)
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

# === API 엔드포인트 ===
@app.route('/admin/check_connection')
def check_connection():
    """데이터베이스 연결 상태 확인"""
    if 'user_id' not in session or not session.get('is_admin'):
        return jsonify({'success': False, 'message': '관리자 권한이 필요합니다.'})
    
    try:
        conn, db_type = get_db_connection()
        
        if db_type == 'postgresql':
            cursor = conn.cursor()
            cursor.execute('SELECT version()')
            version = cursor.fetchone()[0]
            conn.close()
            
            return jsonify({
                'success': True,
                'database': 'PostgreSQL (Supabase)',
                'status': '✅ 연결됨',
                'version': version,
                'message': 'Supabase PostgreSQL에 성공적으로 연결되었습니다!'
            })
        else:
            cursor = conn.cursor()
            cursor.execute('SELECT sqlite_version()')
            version = cursor.fetchone()[0]
            conn.close()
            
            return jsonify({
                'success': True,
                'database': 'SQLite (로컬)',
                'status': '⚠️ 임시 연결',
                'version': f'SQLite {version}',
                'message': 'SQLite에 연결됨 (Supabase 연결 실패 또는 미설정)'
            })
            
    except Exception as e:
        return jsonify({
            'success': False,
            'database': '알 수 없음',
            'status': '❌ 연결 실패',
            'message': f'데이터베이스 연결 오류: {str(e)}'
        })

@app.route('/admin/migrate_to_supabase')
def migrate_to_supabase():
    """SQLite → Supabase 마이그레이션"""
    if 'user_id' not in session or not session.get('is_admin'):
        return jsonify({'success': False, 'message': '관리자 권한이 필요합니다.'})
    
    if not DATABASE_URL or not PSYCOPG2_AVAILABLE:
        return jsonify({
            'success': False, 
            'message': 'SUPABASE_DB_URL 환경변수가 설정되지 않았거나 psycopg2가 설치되지 않았습니다.'
        })
    
    try:
        # SQLite에서 데이터 읽기
        sqlite_conn = sqlite3.connect('warehouse.db')
        sqlite_cursor = sqlite_conn.cursor()
        
        # PostgreSQL 연결
        pg_conn = psycopg2.connect(DATABASE_URL)
        pg_cursor = pg_conn.cursor()
        
        # 사용자 데이터 마이그레이션
        sqlite_cursor.execute('SELECT name, employee_id, team, password, is_approved, created_at FROM users')
        users = sqlite_cursor.fetchall()
        
        for user in users:
            pg_cursor.execute('''INSERT INTO users (name, employee_id, team, password, is_approved, created_at) 
                                VALUES (%s, %s, %s, %s, %s, %s) ON CONFLICT (employee_id) DO NOTHING''', user)
        
        # 재고 데이터 마이그레이션
        sqlite_cursor.execute('SELECT warehouse, category, part_name, quantity, last_modifier, last_modified FROM inventory')
        inventory = sqlite_cursor.fetchall()
        
        for item in inventory:
            pg_cursor.execute('''INSERT INTO inventory (warehouse, category, part_name, quantity, last_modifier, last_modified) 
                                VALUES (%s, %s, %s, %s, %s, %s)''', item)
        
        pg_conn.commit()
        sqlite_conn.close()
        pg_conn.close()
        
        return jsonify({
            'success': True,
            'message': f'✅ 마이그레이션 완료!\n👥 사용자: {len(users)}명\n📦 재고: {len(inventory)}개'
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'마이그레이션 오류: {str(e)}'})

# === 기존 라우트들 ===
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        team = request.form['team']
        employee_number = request.form['employee_number']
        password = request.form['password']

        # 비밀번호 길이 검증
        if len(password) < 8:
            flash('비밀번호는 8자리 이상이어야 합니다.')
            return render_template('register.html')

        # 사번 검증
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
            conn, db_type = get_db_connection()
            
            if db_type == 'postgresql':
                cursor = conn.cursor()
                cursor.execute('SELECT id FROM users WHERE employee_id = %s', (employee_number,))
                if cursor.fetchone():
                    flash('이미 등록된 사번입니다.')
                    conn.close()
                    return render_template('register.html')

                hashed_password = generate_password_hash(password)
                cursor.execute('INSERT INTO users (name, employee_id, team, password) VALUES (%s, %s, %s, %s)',
                              (name, employee_number, team, hashed_password))
            else:
                cursor = conn.cursor()
                cursor.execute('SELECT id FROM users WHERE employee_id = ?', (employee_number,))
                if cursor.fetchone():
                    flash('이미 등록된 사번입니다.')
                    conn.close()
                    return render_template('register.html')

                hashed_password = generate_password_hash(password)
                cursor.execute('INSERT INTO users (name, employee_id, team, password) VALUES (?, ?, ?, ?)',
                              (name, employee_number, team, hashed_password))
            
            conn.commit()
            conn.close()
            flash('회원가입이 완료되었습니다. 관리자 승인 후 이용 가능합니다.')
            return redirect(url_for('index'))
            
        except Exception as e:
            flash('회원가입 중 오류가 발생했습니다.')
            return render_template('register.html')

    return render_template('register.html')

@app.route('/login', methods=['POST'])
def login():
    try:
        employee_id = request.form.get('employee_id', '')
        password = request.form.get('password', '')

        if not employee_id or not password:
            flash('아이디와 비밀번호를 입력해주세요.')
            return redirect(url_for('index'))

        conn, db_type = get_db_connection()
        
        if db_type == 'postgresql':
            cursor = conn.cursor()
            cursor.execute('SELECT id, name, employee_id, password, is_approved FROM users WHERE employee_id = %s', (employee_id,))
        else:
            cursor = conn.cursor()
            cursor.execute('SELECT id, name, employee_id, password, is_approved FROM users WHERE employee_id = ?', (employee_id,))
        
        user = cursor.fetchone()
        conn.close()

        if user and check_password_hash(user[3], password):
            if user[4] == 0:
                flash('관리자 승인 대기 중입니다.')
                return redirect(url_for('index'))

            session.clear()
            session['user_id'] = user[0]
            session['user_name'] = user[1]
            session['employee_id'] = user[2]
            session['is_admin'] = (employee_id == 'admin')
            session.permanent = True

            if session['is_admin']:
                return redirect(url_for('admin_dashboard'))
            else:
                return redirect(url_for('dashboard'))
        else:
            flash('아이디 또는 비밀번호가 잘못되었습니다.')
            return redirect(url_for('index'))
            
    except Exception as e:
        flash('로그인 중 오류가 발생했습니다. 다시 시도해주세요.')
        return redirect(url_for('index'))

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('index'))

    if session.get('is_admin') == True:
        return redirect(url_for('admin_dashboard'))

    return render_template('dashboard.html')

@app.route('/admin_dashboard')
def admin_dashboard():
    if 'user_id' not in session:
        flash('로그인이 필요합니다.')
        return redirect(url_for('index'))

    if not session.get('is_admin'):
        flash('관리자 권한이 필요합니다.')
        return redirect(url_for('dashboard'))

    try:
        conn, db_type = get_db_connection()
        
        if db_type == 'postgresql':
            cursor = conn.cursor()
            cursor.execute('SELECT id, name, employee_id, team, is_approved, created_at FROM users WHERE employee_id != %s', ('admin',))
        else:
            cursor = conn.cursor()
            cursor.execute('SELECT id, name, employee_id, team, is_approved, created_at FROM users WHERE employee_id != ?', ('admin',))
        
        users = cursor.fetchall()
        conn.close()
        
        return render_template('admin_dashboard.html', users=users)
        
    except Exception as e:
        flash('데이터를 불러오는 중 오류가 발생했습니다.')
        return redirect(url_for('index'))

@app.route('/approve_user/<int:user_id>')
def approve_user(user_id):
    if 'user_id' not in session or not session.get('is_admin'):
        return redirect(url_for('index'))

    try:
        conn, db_type = get_db_connection()
        
        if db_type == 'postgresql':
            cursor = conn.cursor()
            cursor.execute('UPDATE users SET is_approved = %s WHERE id = %s', (1, user_id))
        else:
            cursor = conn.cursor()
            cursor.execute('UPDATE users SET is_approved = 1 WHERE id = ?', (user_id,))
        
        conn.commit()
        conn.close()
        flash('사용자가 승인되었습니다.')
        
    except Exception as e:
        flash('사용자 승인 중 오류가 발생했습니다.')
    
    return redirect(url_for('admin_dashboard'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

# 헬스체크 엔드포인트
@app.route('/health')
def health():
    conn, db_type = get_db_connection()
    conn.close()
    
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'database': db_type,
        'supabase_url_set': bool(DATABASE_URL),
        'psycopg2_available': PSYCOPG2_AVAILABLE,
        'message': f'SK오앤에스 창고관리 시스템 ({db_type}) 정상 작동 중'
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    is_render = os.environ.get('RENDER') is not None
    
    print("🚀 SK오앤에스 창고관리 시스템 시작")
    print(f"📱 포트: {port}")
    print(f"🗄️ 데이터베이스: {'Supabase 설정됨' if DATABASE_URL else 'SQLite 모드'}")
    print(f"📦 psycopg2: {'설치됨' if PSYCOPG2_AVAILABLE else '미설치'}")
    
    if is_render:
        app.run(host='0.0.0.0', port=port, debug=False)
    else:
        app.run(debug=True, host='0.0.0.0', port=5000, threaded=True)
