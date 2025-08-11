from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, send_file
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import sqlite3
import psycopg2
import psycopg2.extras
import os
import socket
import webbrowser
import threading
import time
from datetime import datetime, timedelta
import uuid
import pytz

app = Flask(__name__)
app.secret_key = 'sk_ons_warehouse_secret_key_2025'
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# 업로드 폴더 생성
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# 데이터베이스 연결 정보
DATABASE_URL = os.environ.get('SUPABASE_DB_URL')  # Render 환경변수에서 가져오기

def get_db_connection():
    """데이터베이스 연결 - Supabase 우선, 없으면 SQLite"""
    if DATABASE_URL:
        try:
            conn = psycopg2.connect(DATABASE_URL)
            return conn, 'postgresql'
        except Exception as e:
            print(f"PostgreSQL 연결 실패, SQLite로 폴백: {e}")
            return sqlite3.connect('warehouse.db'), 'sqlite'
    else:
        return sqlite3.connect('warehouse.db'), 'sqlite'

def execute_query(query, params=(), fetch=False, fetchall=False, commit=True):
    """범용 쿼리 실행 함수"""
    conn, db_type = get_db_connection()
    
    try:
        if db_type == 'postgresql':
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cursor.execute(query, params)
        else:
            cursor = conn.cursor()
            cursor.execute(query, params)
        
        result = None
        if fetch:
            result = cursor.fetchone()
        elif fetchall:
            result = cursor.fetchall()
        
        if commit:
            conn.commit()
        
        return result
    except Exception as e:
        print(f"쿼리 실행 오류: {e}")
        conn.rollback()
        raise e
    finally:
        conn.close()

def get_local_ip():
    """로컬 IP 주소를 가져옵니다."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"

def get_korea_time():
    """한국시간(KST)을 반환합니다."""
    korea_tz = pytz.timezone('Asia/Seoul')
    return datetime.now(korea_tz)

def format_korea_time(utc_time_str):
    """UTC 시간 문자열을 한국시간으로 변환하여 포맷팅합니다."""
    if not utc_time_str:
        return '미설정'
    
    try:
        # UTC 시간을 파싱
        utc_time = datetime.strptime(utc_time_str, '%Y-%m-%d %H:%M:%S')
        utc_time = pytz.utc.localize(utc_time)
        
        # 한국시간으로 변환
        korea_tz = pytz.timezone('Asia/Seoul')
        korea_time = utc_time.astimezone(korea_tz)
        
        return korea_time.strftime('%Y-%m-%d %H:%M:%S')
    except:
        return utc_time_str

def open_browser():
    """3초 후 브라우저를 자동으로 엽니다."""
    time.sleep(3)
    local_ip = get_local_ip()
    urls = [
        f"http://storageborame.net:5000",
        f"http://{local_ip}:5000",
        "http://localhost:5000"
    ]

    for url in urls:
        try:
            webbrowser.open(url)
            break
        except:
            continue

# 허용된 파일 확장자
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def init_db():
    """데이터베이스 초기화 - Supabase와 SQLite 모두 지원"""
    try:
        print("데이터베이스 초기화 시작...")
        conn, db_type = get_db_connection()
        
        if db_type == 'postgresql':
            cursor = conn.cursor()
            print("✅ PostgreSQL (Supabase) 연결 성공!")
            
            # PostgreSQL용 테이블 생성
            # 사용자 테이블
            cursor.execute('''CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                employee_id TEXT UNIQUE NOT NULL,
                team TEXT NOT NULL,
                password TEXT NOT NULL,
                is_approved INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT (NOW() AT TIME ZONE 'Asia/Seoul')
            )''')

            # 창고 재고 테이블
            cursor.execute('''CREATE TABLE IF NOT EXISTS inventory (
                id SERIAL PRIMARY KEY,
                warehouse TEXT NOT NULL,
                category TEXT NOT NULL,
                part_name TEXT NOT NULL,
                quantity INTEGER DEFAULT 0,
                last_modifier TEXT,
                last_modified TIMESTAMP DEFAULT (NOW() AT TIME ZONE 'Asia/Seoul')
            )''')

            # 재고 변경 이력 테이블
            cursor.execute('''CREATE TABLE IF NOT EXISTS inventory_history (
                id SERIAL PRIMARY KEY,
                inventory_id INTEGER REFERENCES inventory(id),
                change_type TEXT,
                quantity_change INTEGER,
                modifier_name TEXT,
                modified_at TIMESTAMP DEFAULT (NOW() AT TIME ZONE 'Asia/Seoul')
            )''')

            # 사진 테이블
            cursor.execute('''CREATE TABLE IF NOT EXISTS photos (
                id SERIAL PRIMARY KEY,
                inventory_id INTEGER REFERENCES inventory(id),
                filename TEXT NOT NULL,
                original_name TEXT NOT NULL,
                file_size INTEGER,
                uploaded_by TEXT,
                uploaded_at TIMESTAMP DEFAULT (NOW() AT TIME ZONE 'Asia/Seoul')
            )''')

            # 관리자 계정 생성
            admin_password = generate_password_hash('Onsn1103813!')
            cursor.execute('''INSERT INTO users (name, employee_id, team, password, is_approved) 
                             VALUES (%s, %s, %s, %s, %s) ON CONFLICT (employee_id) DO NOTHING''',
                          ('관리자', 'admin', '관리', admin_password, 1))
            
        else:
            cursor = conn.cursor()
            print("✅ SQLite 연결 성공!")
            
            # SQLite용 테이블 생성 (기존 코드)
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

            cursor.execute('''CREATE TABLE IF NOT EXISTS inventory_history
                             (id INTEGER PRIMARY KEY AUTOINCREMENT,
                              inventory_id INTEGER,
                              change_type TEXT,
                              quantity_change INTEGER,
                              modifier_name TEXT,
                              modified_at TEXT DEFAULT (datetime('now', '+9 hours')),
                              FOREIGN KEY (inventory_id) REFERENCES inventory (id))''')

            cursor.execute('''CREATE TABLE IF NOT EXISTS photos
                             (id INTEGER PRIMARY KEY AUTOINCREMENT,
                              inventory_id INTEGER,
                              filename TEXT NOT NULL,
                              original_name TEXT NOT NULL,
                              file_size INTEGER,
                              uploaded_by TEXT,
                              uploaded_at TEXT DEFAULT (datetime('now', '+9 hours')),
                              FOREIGN KEY (inventory_id) REFERENCES inventory (id))''')

            # 관리자 계정 생성
            admin_password = generate_password_hash('Onsn1103813!')
            cursor.execute('INSERT OR IGNORE INTO users (name, employee_id, team, password, is_approved) VALUES (?, ?, ?, ?, ?)',
                          ('관리자', 'admin', '관리', admin_password, 1))

        conn.commit()
        conn.close()
        print(f"✅ 데이터베이스 초기화 완료! ({db_type})")
        
    except Exception as e:
        print(f"❌ 데이터베이스 초기화 오류: {e}")

# 앱 시작 시 즉시 데이터베이스 초기화
init_db()

# === 새로운 관리자 기능: 연결 상태 확인 ===
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
                'message': 'SQLite에 연결됨 (Supabase 연결 실패)'
            })
            
    except Exception as e:
        return jsonify({
            'success': False,
            'database': '알 수 없음',
            'status': '❌ 연결 실패',
            'message': f'데이터베이스 연결 오류: {str(e)}'
        })

# === 새로운 관리자 기능: SQLite → Supabase 마이그레이션 ===
@app.route('/admin/migrate_to_supabase')
def migrate_to_supabase():
    """SQLite 데이터를 Supabase로 마이그레이션"""
    if 'user_id' not in session or not session.get('is_admin'):
        return jsonify({'success': False, 'message': '관리자 권한이 필요합니다.'})
    
    if not DATABASE_URL:
        return jsonify({'success': False, 'message': 'SUPABASE_DB_URL 환경변수가 설정되지 않았습니다.'})
    
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
        
        # 재고 이력 마이그레이션 (inventory_id 매핑 필요)
        # 간단히 하기 위해 이력은 스키프하고 재고만 마이그레이션
        
        pg_conn.commit()
        sqlite_conn.close()
        pg_conn.close()
        
        return jsonify({
            'success': True,
            'message': f'✅ 마이그레이션 완료!\n👥 사용자: {len(users)}명\n📦 재고: {len(inventory)}개'
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'마이그레이션 오류: {str(e)}'})

# === 기존 라우트들 (수정된 부분만) ===

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

# ... 나머지 라우트들은 동일한 패턴으로 수정 ...
# (warehouse, electric_inventory, add_inventory_item 등)

@app.route('/warehouse/<warehouse_name>')
def warehouse(warehouse_name):
    if 'user_id' not in session:
        return redirect(url_for('index'))

    if warehouse_name != '보라매창고':
        return render_template('preparing.html', warehouse_name=warehouse_name)

    return render_template('warehouse.html', warehouse_name=warehouse_name)

@app.route('/warehouse/<warehouse_name>/electric')
def electric_inventory(warehouse_name):
    if 'user_id' not in session:
        return redirect(url_for('index'))

    if warehouse_name != '보라매창고':
        return render_template('preparing.html', warehouse_name=warehouse_name)

    try:
        conn, db_type = get_db_connection()
        
        if db_type == 'postgresql':
            cursor = conn.cursor()
            cursor.execute('''SELECT i.id, i.category, i.part_name, i.quantity, i.last_modifier, i.last_modified,
                                    COUNT(p.id) as photo_count
                             FROM inventory i
                             LEFT JOIN photos p ON i.id = p.inventory_id
                             WHERE i.warehouse = %s AND i.category = %s
                             GROUP BY i.id
                             ORDER BY i.id''', (warehouse_name, "전기차"))
        else:
            cursor = conn.cursor()
            cursor.execute('''SELECT i.id, i.category, i.part_name, i.quantity, i.last_modifier, i.last_modified,
                                    COUNT(p.id) as photo_count
                             FROM inventory i
                             LEFT JOIN photos p ON i.id = p.inventory_id
                             WHERE i.warehouse = ? AND i.category = "전기차"
                             GROUP BY i.id
                             ORDER BY i.id''', (warehouse_name,))
        
        inventory = cursor.fetchall()
        conn.close()
        
        return render_template('electric_inventory.html',
                               warehouse_name=warehouse_name,
                               inventory=inventory,
                               is_admin=session.get('is_admin', False))
                               
    except Exception as e:
        flash('재고 정보를 불러오는 중 오류가 발생했습니다.')
        return redirect(url_for('dashboard'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

# 에러 핸들러
@app.errorhandler(500)
def internal_error(error):
    return '''
    <html>
    <head><title>서버 오류</title></head>
    <body>
        <h1>서버 내부 오류</h1>
        <p>죄송합니다. 서버에서 오류가 발생했습니다.</p>
        <p><a href="/">홈으로 돌아가기</a></p>
    </body>
    </html>
    ''', 500

@app.errorhandler(404)
def page_not_found(error):
    return '''
    <html>
    <head><title>페이지를 찾을 수 없음</title></head>
    <body>
        <h1>404 - 페이지를 찾을 수 없습니다</h1>
        <p><a href="/">홈으로 돌아가기</a></p>
    </body>
    </html>
    ''', 404

@app.route('/delete_user/<int:user_id>')
def delete_user(user_id):
    if 'user_id' not in session or not session.get('is_admin'):
        flash('관리자 권한이 필요합니다.')
        return redirect(url_for('index'))

    try:
        conn, db_type = get_db_connection()
        
        if db_type == 'postgresql':
            cursor = conn.cursor()
            cursor.execute('SELECT name, employee_id FROM users WHERE id = %s AND employee_id != %s', (user_id, 'admin'))
            user = cursor.fetchone()
            
            if user:
                cursor.execute('DELETE FROM users WHERE id = %s', (user_id,))
                conn.commit()
                flash(f'사용자 {user[0]}({user[1]})가 삭제되었습니다.')
            else:
                flash('삭제할 수 없는 사용자입니다.')
        else:
            cursor = conn.cursor()
            cursor.execute('SELECT name, employee_id FROM users WHERE id = ? AND employee_id != "admin"', (user_id,))
            user = cursor.fetchone()
            
            if user:
                cursor.execute('DELETE FROM users WHERE id = ?', (user_id,))
                conn.commit()
                flash(f'사용자 {user[0]}({user[1]})가 삭제되었습니다.')
            else:
                flash('삭제할 수 없는 사용자입니다.')
        
        conn.close()
        
    except Exception as e:
        flash('사용자 삭제 중 오류가 발생했습니다.')
    
    return redirect(url_for('admin_dashboard'))

@app.route('/add_inventory_item', methods=['POST'])
def add_inventory_item():
    if 'user_id' not in session or not session.get('is_admin'):
        return redirect(url_for('index'))

    warehouse_name = request.form['warehouse_name']
    category = request.form['category']
    part_name = request.form['part_name']
    quantity = int(request.form['quantity'])

    korea_time = get_korea_time().strftime('%Y-%m-%d %H:%M:%S')

    try:
        conn, db_type = get_db_connection()
        
        if db_type == 'postgresql':
            cursor = conn.cursor()
            cursor.execute('INSERT INTO inventory (warehouse, category, part_name, quantity, last_modifier, last_modified) VALUES (%s, %s, %s, %s, %s, %s)',
                          (warehouse_name, category, part_name, quantity, session['user_name'], korea_time))
        else:
            cursor = conn.cursor()
            cursor.execute('INSERT INTO inventory (warehouse, category, part_name, quantity, last_modifier, last_modified) VALUES (?, ?, ?, ?, ?, ?)',
                          (warehouse_name, category, part_name, quantity, session['user_name'], korea_time))
        
        conn.commit()
        conn.close()
        
    except Exception as e:
        flash('재고 추가 중 오류가 발생했습니다.')
    
    return redirect(url_for('electric_inventory', warehouse_name=warehouse_name))

@app.route('/delete_inventory_item/<int:item_id>')
def delete_inventory_item(item_id):
    if 'user_id' not in session or not session.get('is_admin'):
        flash('관리자 권한이 필요합니다.')
        return redirect(url_for('index'))

    try:
        conn, db_type = get_db_connection()
        
        if db_type == 'postgresql':
            cursor = conn.cursor()
            cursor.execute('SELECT warehouse, category, part_name FROM inventory WHERE id = %s', (item_id,))
            item = cursor.fetchone()
            
            if item:
                warehouse_name, category, part_name = item
                
                # 관련 사진들 삭제
                cursor.execute('SELECT filename FROM photos WHERE inventory_id = %s', (item_id,))
                photos = cursor.fetchall()
                
                for photo in photos:
                    file_path = os.path.join(app.config['UPLOAD_FOLDER'], photo[0])
                    if os.path.exists(file_path):
                        try:
                            os.remove(file_path)
                        except Exception as e:
                            print(f"사진 파일 삭제 실패: {e}")
                
                cursor.execute('DELETE FROM photos WHERE inventory_id = %s', (item_id,))
                cursor.execute('DELETE FROM inventory_history WHERE inventory_id = %s', (item_id,))
                cursor.execute('DELETE FROM inventory WHERE id = %s', (item_id,))
                
                conn.commit()
                flash(f'물품 "{part_name}"이(가) 삭제되었습니다.')
                
                return redirect(url_for('electric_inventory', warehouse_name=warehouse_name))
            else:
                flash('삭제할 물품을 찾을 수 없습니다.')
        else:
            cursor = conn.cursor()
            cursor.execute('SELECT warehouse, category, part_name FROM inventory WHERE id = ?', (item_id,))
            item = cursor.fetchone()
            
            if item:
                warehouse_name, category, part_name = item
                
                # 관련 사진들 삭제
                cursor.execute('SELECT filename FROM photos WHERE inventory_id = ?', (item_id,))
                photos = cursor.fetchall()
                
                for photo in photos:
                    file_path = os.path.join(app.config['UPLOAD_FOLDER'], photo[0])
                    if os.path.exists(file_path):
                        try:
                            os.remove(file_path)
                        except Exception as e:
                            print(f"사진 파일 삭제 실패: {e}")
                
                cursor.execute('DELETE FROM photos WHERE inventory_id = ?', (item_id,))
                cursor.execute('DELETE FROM inventory_history WHERE inventory_id = ?', (item_id,))
                cursor.execute('DELETE FROM inventory WHERE id = ?', (item_id,))
                
                conn.commit()
                flash(f'물품 "{part_name}"이(가) 삭제되었습니다.')
                
                return redirect(url_for('electric_inventory', warehouse_name=warehouse_name))
            else:
                flash('삭제할 물품을 찾을 수 없습니다.')
        
        conn.close()
        
    except Exception as e:
        flash('물품 삭제 중 오류가 발생했습니다.')
    
    return redirect(url_for('dashboard'))

@app.route('/edit_inventory_item/<int:item_id>', methods=['GET', 'POST'])
def edit_inventory_item(item_id):
    if 'user_id' not in session or not session.get('is_admin'):
        flash('관리자 권한이 필요합니다.')
        return redirect(url_for('index'))

    conn, db_type = get_db_connection()

    if request.method == 'POST':
        part_name = request.form['part_name']
        quantity = int(request.form['quantity'])
        
        try:
            korea_time = get_korea_time().strftime('%Y-%m-%d %H:%M:%S')
            
            if db_type == 'postgresql':
                cursor = conn.cursor()
                cursor.execute('UPDATE inventory SET part_name = %s, quantity = %s, last_modifier = %s, last_modified = %s WHERE id = %s',
                              (part_name, quantity, session['user_name'], korea_time, item_id))
                cursor.execute('INSERT INTO inventory_history (inventory_id, change_type, quantity_change, modifier_name, modified_at) VALUES (%s, %s, %s, %s, %s)',
                              (item_id, 'edit', 0, session['user_name'], korea_time))
            else:
                cursor = conn.cursor()
                cursor.execute('UPDATE inventory SET part_name = ?, quantity = ?, last_modifier = ?, last_modified = ? WHERE id = ?',
                              (part_name, quantity, session['user_name'], korea_time, item_id))
                cursor.execute('INSERT INTO inventory_history (inventory_id, change_type, quantity_change, modifier_name, modified_at) VALUES (?, ?, ?, ?, ?)',
                              (item_id, 'edit', 0, session['user_name'], korea_time))
            
            conn.commit()
            flash(f'물품 "{part_name}"이(가) 수정되었습니다.')
            
            # 수정 후 원래 페이지로 돌아가기
            if db_type == 'postgresql':
                cursor.execute('SELECT warehouse FROM inventory WHERE id = %s', (item_id,))
            else:
                cursor.execute('SELECT warehouse FROM inventory WHERE id = ?', (item_id,))
            
            warehouse = cursor.fetchone()
            conn.close()
            
            if warehouse:
                return redirect(url_for('electric_inventory', warehouse_name=warehouse[0]))
            else:
                return redirect(url_for('dashboard'))
                
        except Exception as e:
            flash('물품 수정 중 오류가 발생했습니다.')
            conn.close()
            return redirect(url_for('dashboard'))
    
    else:
        # 수정 폼 표시
        try:
            if db_type == 'postgresql':
                cursor = conn.cursor()
                cursor.execute('SELECT warehouse, category, part_name, quantity FROM inventory WHERE id = %s', (item_id,))
            else:
                cursor = conn.cursor()
                cursor.execute('SELECT warehouse, category, part_name, quantity FROM inventory WHERE id = ?', (item_id,))
            
            item = cursor.fetchone()
            conn.close()
            
            if item:
                return render_template('edit_inventory.html', 
                                     item_id=item_id,
                                     warehouse=item[0], 
                                     category=item[1], 
                                     part_name=item[2], 
                                     quantity=item[3])
            else:
                flash('수정할 물품을 찾을 수 없습니다.')
                return redirect(url_for('dashboard'))
                
        except Exception as e:
            flash('물품 정보를 불러오는 중 오류가 발생했습니다.')
            return redirect(url_for('dashboard'))

@app.route('/update_quantity', methods=['POST'])
def update_quantity():
    if 'user_id' not in session:
        return redirect(url_for('index'))

    data = request.get_json()
    item_id = data['item_id']
    change_type = data['change_type']
    quantity_change = int(data['quantity'])

    try:
        conn, db_type = get_db_connection()
        
        if db_type == 'postgresql':
            cursor = conn.cursor()
            cursor.execute('SELECT quantity, warehouse FROM inventory WHERE id = %s', (item_id,))
        else:
            cursor = conn.cursor()
            cursor.execute('SELECT quantity, warehouse FROM inventory WHERE id = ?', (item_id,))
        
        current_quantity, warehouse = cursor.fetchone()

        if change_type == 'out':
            quantity_change = -quantity_change
            if current_quantity + quantity_change < 0:
                conn.close()
                return jsonify({'success': False, 'message': '재고가 부족합니다.'})

        new_quantity = current_quantity + quantity_change
        korea_time = get_korea_time().strftime('%Y-%m-%d %H:%M:%S')

        if db_type == 'postgresql':
            cursor.execute('UPDATE inventory SET quantity = %s, last_modifier = %s, last_modified = %s WHERE id = %s',
                          (new_quantity, session['user_name'], korea_time, item_id))
            cursor.execute('INSERT INTO inventory_history (inventory_id, change_type, quantity_change, modifier_name, modified_at) VALUES (%s, %s, %s, %s, %s)',
                          (item_id, change_type, quantity_change, session['user_name'], korea_time))
        else:
            cursor.execute('UPDATE inventory SET quantity = ?, last_modifier = ?, last_modified = ? WHERE id = ?',
                          (new_quantity, session['user_name'], korea_time, item_id))
            cursor.execute('INSERT INTO inventory_history (inventory_id, change_type, quantity_change, modifier_name, modified_at) VALUES (?, ?, ?, ?, ?)',
                          (item_id, change_type, quantity_change, session['user_name'], korea_time))

        conn.commit()
        conn.close()

        return jsonify({'success': True, 'new_quantity': new_quantity})
        
    except Exception as e:
        return jsonify({'success': False, 'message': '수량 업데이트 중 오류가 발생했습니다.'})

@app.route('/upload_photo/<int:item_id>', methods=['POST'])
def upload_photo(item_id):
    if 'user_id' not in session:
        return redirect(url_for('index'))

    if 'photo' not in request.files:
        return jsonify({'success': False, 'message': '파일이 선택되지 않았습니다.'})

    file = request.files['photo']
    if file.filename == '':
        return jsonify({'success': False, 'message': '파일이 선택되지 않았습니다.'})

    if file and allowed_file(file.filename):
        filename = str(uuid.uuid4()) + '.' + file.filename.rsplit('.', 1)[1].lower()
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)

        file_size = os.path.getsize(file_path) // 1024

        try:
            conn, db_type = get_db_connection()
            
            if db_type == 'postgresql':
                cursor = conn.cursor()
                cursor.execute('INSERT INTO photos (inventory_id, filename, original_name, file_size, uploaded_by) VALUES (%s, %s, %s, %s, %s)',
                              (item_id, filename, file.filename, file_size, session['user_name']))
            else:
                cursor = conn.cursor()
                cursor.execute('INSERT INTO photos (inventory_id, filename, original_name, file_size, uploaded_by) VALUES (?, ?, ?, ?, ?)',
                              (item_id, filename, file.filename, file_size, session['user_name']))
            
            conn.commit()
            conn.close()

            return jsonify({'success': True, 'message': '사진이 업로드되었습니다.'})
            
        except Exception as e:
            return jsonify({'success': False, 'message': '사진 업로드 중 오류가 발생했습니다.'})

    return jsonify({'success': False, 'message': '지원하지 않는 파일 형식입니다.'})

@app.route('/photos/<int:item_id>')
def view_photos(item_id):
    if 'user_id' not in session:
        return redirect(url_for('index'))

    try:
        conn, db_type = get_db_connection()
        
        if db_type == 'postgresql':
            cursor = conn.cursor()
            cursor.execute('SELECT id, filename, original_name, file_size, uploaded_by, uploaded_at FROM photos WHERE inventory_id = %s', (item_id,))
        else:
            cursor = conn.cursor()
            cursor.execute('SELECT id, filename, original_name, file_size, uploaded_by, uploaded_at FROM photos WHERE inventory_id = ?', (item_id,))
        
        photos = cursor.fetchall()
        conn.close()

        return render_template('photos.html', photos=photos, item_id=item_id, is_admin=session.get('is_admin', False))
        
    except Exception as e:
        flash('사진 정보를 불러오는 중 오류가 발생했습니다.')
        return redirect(url_for('dashboard'))

@app.route('/download_photo/<int:photo_id>')
def download_photo(photo_id):
    if 'user_id' not in session or not session.get('is_admin'):
        return redirect(url_for('index'))

    try:
        conn, db_type = get_db_connection()
        
        if db_type == 'postgresql':
            cursor = conn.cursor()
            cursor.execute('SELECT filename, original_name FROM photos WHERE id = %s', (photo_id,))
        else:
            cursor = conn.cursor()
            cursor.execute('SELECT filename, original_name FROM photos WHERE id = ?', (photo_id,))
        
        photo = cursor.fetchone()
        conn.close()

        if photo:
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], photo[0])
            return send_file(file_path, as_attachment=True, download_name=photo[1])

        flash('파일을 찾을 수 없습니다.')
        return redirect(request.referrer)
        
    except Exception as e:
        flash('파일 다운로드 중 오류가 발생했습니다.')
        return redirect(request.referrer)

@app.route('/delete_photo/<int:photo_id>')
def delete_photo(photo_id):
    if 'user_id' not in session or not session.get('is_admin'):
        return redirect(url_for('index'))

    try:
        conn, db_type = get_db_connection()
        
        if db_type == 'postgresql':
            cursor = conn.cursor()
            cursor.execute('SELECT filename, inventory_id FROM photos WHERE id = %s', (photo_id,))
        else:
            cursor = conn.cursor()
            cursor.execute('SELECT filename, inventory_id FROM photos WHERE id = ?', (photo_id,))
        
        photo = cursor.fetchone()

        if photo:
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], photo[0])
            if os.path.exists(file_path):
                os.remove(file_path)

            if db_type == 'postgresql':
                cursor.execute('DELETE FROM photos WHERE id = %s', (photo_id,))
            else:
                cursor.execute('DELETE FROM photos WHERE id = ?', (photo_id,))
            
            conn.commit()
            flash('사진이 삭제되었습니다.')

        conn.close()
        
    except Exception as e:
        flash('사진 삭제 중 오류가 발생했습니다.')
    
    return redirect(request.referrer)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    is_render = os.environ.get('RENDER') is not None
    
    if is_render:
        print("🚀 SK오앤에스 창고관리 시스템 (Render.com 배포)")
        print(f"🌐 포트 {port}에서 서비스 시작...")
        print("✅ 외부 접속 가능한 URL로 서비스됩니다.")
        
        if DATABASE_URL:
            print("✅ Supabase PostgreSQL 연결 설정됨")
        else:
            print("⚠️ SQLite 모드로 실행 (SUPABASE_DB_URL 미설정)")
        
        app.run(host='0.0.0.0', port=port, debug=False)
        
    else:
        local_ip = get_local_ip()
        print("=" * 60)
        print("🚀 SK오앤에스 창고관리 시스템을 시작합니다!")
        print("=" * 60)
        print(f"📱 접속: http://localhost:5000")
        if DATABASE_URL:
            print("✅ Supabase 모드")
        else:
            print("⚠️ SQLite 모드")
        print("=" * 60)

        threading.Thread(target=open_browser, daemon=True).start()

        try:
            app.run(debug=True, host='0.0.0.0', port=5000, threaded=True)
        except KeyboardInterrupt:
            print("\n👋 시스템을 종료합니다. 감사합니다!")
        except Exception as e:
            print(f"\n❌ 오류가 발생했습니다: {e}")
