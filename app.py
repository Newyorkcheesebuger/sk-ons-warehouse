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
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'Onsn1103813!')

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
# 라우트 정의 (무한 리디렉션 완전 해결)
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
    """관리자 전용 대시보드 - 수정된 버전"""
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
        
        # 🔧 수정: SQL 쿼리 단순화
        cursor.execute("SELECT id, name, employee_id, team, is_approved, created_at FROM users WHERE employee_id != %s ORDER BY created_at DESC", ('admin',))
        users = cursor.fetchall()
        
        # 재고 통계 - 단순화
        cursor.execute("SELECT COUNT(*) FROM inventory")
        result = cursor.fetchone()
        total_items = result[0] if result else 0
        
        cursor.execute("SELECT SUM(quantity) FROM inventory")
        result = cursor.fetchone() 
        total_quantity = result[0] if result and result[0] else 0
        
        cursor.execute("SELECT warehouse, COUNT(*) FROM inventory GROUP BY warehouse")
        warehouse_stats = cursor.fetchall()
        
        conn.close()
        
        # 안전한 데이터 구조
        warehouse_dict = {}
        if warehouse_stats:
            for stat in warehouse_stats:
                warehouse_dict[stat[0]] = stat[1]
        
        return render_template('admin_dashboard.html', 
                             users=users or [],
                             total_items=total_items,
                             total_quantity=total_quantity,
                             warehouse_stats=warehouse_dict)
        
    except Exception as e:
        print(f"❌ 관리자 대시보드 상세 오류: {type(e).__name__}: {str(e)}")
        # 🔧 무한 루프 방지: 간단한 HTML 반환
        return f"""
        <html>
        <head><title>관리자 대시보드</title></head>
        <body style="font-family: Arial, sans-serif; padding: 20px;">
            <h1>🔧 관리자 대시보드 (임시)</h1>
            <p>환영합니다, {session.get('user_name')}님!</p>
            <p>시스템에 일시적인 문제가 있습니다.</p>
            <p>오류: {str(e)}</p>
            <a href="/logout">로그아웃</a>
        </body>
        </html>
        """

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

@app.route('/admin/warehouse')
def admin_warehouse():
    """관리자용 창고 관리 페이지"""
    if 'user_id' not in session:
        flash('로그인이 필요합니다.')
        return redirect('/')
    
    if not session.get('is_admin'):
        flash('관리자 권한이 필요합니다.')
        return redirect('/dashboard')
    
    print("✅ 관리자 창고 관리 페이지 접근 성공")
    
    # 관리자는 모든 창고에 접근 가능
    return render_template('user_dashboard.html', warehouses=WAREHOUSES)

@app.route('/approve_user/<int:user_id>')
def approve_user(user_id):
    """사용자 승인 (관리자 전용)"""
    if 'user_id' not in session or not session.get('is_admin'):
        flash('관리자 권한이 필요합니다.')
        return redirect('/')

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('UPDATE users SET is_approved = %s WHERE id = %s', (1, user_id))
        conn.commit()
        conn.close()
        flash('사용자가 승인되었습니다.')
        
    except Exception as e:
        flash('사용자 승인 중 오류가 발생했습니다.')
    
    return redirect('/admin/dashboard')

@app.route('/delete_user/<int:user_id>')
def delete_user(user_id):
    """사용자 삭제 (관리자 전용)"""
    if 'user_id' not in session or not session.get('is_admin'):
        flash('관리자 권한이 필요합니다.')
        return redirect('/')

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT name, employee_id FROM users WHERE id = %s AND employee_id != %s', (user_id, 'admin'))
        user = cursor.fetchone()
        
        if user:
            cursor.execute('DELETE FROM users WHERE id = %s', (user_id,))
            conn.commit()
            flash(f'사용자 {user[0]}({user[1]})가 삭제되었습니다.')
        else:
            flash('삭제할 수 없는 사용자입니다.')
        
        conn.close()
        
    except Exception as e:
        flash('사용자 삭제 중 오류가 발생했습니다.')
    
    return redirect('/admin/dashboard')

@app.route('/warehouse/<warehouse_name>')
def warehouse(warehouse_name):
    """창고 선택 페이지"""
    if 'user_id' not in session:
        return redirect('/')

    if warehouse_name not in WAREHOUSES:
        return render_template('preparing.html', warehouse_name=warehouse_name)

    return render_template('warehouse.html', warehouse_name=warehouse_name)

@app.route('/warehouse/<warehouse_name>/electric')
def electric_inventory(warehouse_name):
    """전기차 부품 재고 관리 페이지 - datetime 오류 완전 해결"""
    if 'user_id' not in session:
        return redirect('/')

    print(f"🔍 전기차 부품 재고 접근: {warehouse_name}, 사용자: {session.get('user_name')}")

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''SELECT i.id, i.category, i.part_name, i.quantity, i.last_modifier, i.last_modified,
                                COUNT(p.id) as photo_count
                         FROM inventory i
                         LEFT JOIN photos p ON i.id = p.inventory_id
                         WHERE i.warehouse = %s AND i.category = %s
                         GROUP BY i.id, i.category, i.part_name, i.quantity, i.last_modifier, i.last_modified
                         ORDER BY i.id''', (warehouse_name, "전기차"))
        
        raw_inventory = cursor.fetchall()
        conn.close()
        
        # 🔧 날짜 형식 변환 처리 (datetime 오류 완전 해결)
        inventory = []
        for item in raw_inventory:
            item_list = list(item)
            if item_list[5]:  # last_modified가 존재하면
                if isinstance(item_list[5], str):
                    # 이미 문자열이면 그대로 사용
                    pass
                else:
                    # datetime 객체면 문자열로 변환
                    item_list[5] = item_list[5].strftime('%Y-%m-%d %H:%M:%S')
            inventory.append(item_list)
        
        print(f"✅ 재고 데이터 조회 성공: {len(inventory)}개 항목")
        
        return render_template('electric_inventory.html',
                               warehouse_name=warehouse_name,
                               inventory=inventory,
                               is_admin=session.get('is_admin', False))
                               
    except Exception as e:
        print(f"❌ electric_inventory 오류: {type(e).__name__}: {str(e)}")
        flash('재고 정보를 불러오는 중 오류가 발생했습니다.')
        
        # 🔧 관리자/사용자 구분하여 안전한 리디렉션 (무한 루프 방지)
        if session.get('is_admin'):
            return redirect('/admin/warehouse')
        else:
            return redirect('/dashboard')


@app.route('/add_inventory_item', methods=['POST'])
def add_inventory_item():
    """재고 아이템 추가 (관리자 전용)"""
    if 'user_id' not in session or not session.get('is_admin'):
        flash('관리자 권한이 필요합니다.')
        return redirect('/')

    warehouse_name = request.form['warehouse_name']
    category = request.form['category']
    part_name = request.form['part_name']
    quantity = int(request.form['quantity'])
    korea_time = get_korea_time().strftime('%Y-%m-%d %H:%M:%S')

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('INSERT INTO inventory (warehouse, category, part_name, quantity, last_modifier, last_modified) VALUES (%s, %s, %s, %s, %s, %s)',
                      (warehouse_name, category, part_name, quantity, session['user_name'], korea_time))
        
        conn.commit()
        conn.close()
        flash('재고 아이템이 추가되었습니다.')
        
    except Exception as e:
        flash('재고 추가 중 오류가 발생했습니다.')
    
    return redirect(f'/warehouse/{warehouse_name}/electric')

@app.route('/update_quantity', methods=['POST'])
def update_quantity():
    """재고 수량 업데이트"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': '로그인이 필요합니다.'}), 401

    try:
        data = request.get_json()
        item_id = data['item_id']
        change_type = data['change_type']
        quantity_change = int(data['quantity'])

        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT quantity, warehouse FROM inventory WHERE id = %s', (item_id,))
        result = cursor.fetchone()
        if not result:
            conn.close()
            return jsonify({'success': False, 'message': '재고 항목을 찾을 수 없습니다.'})
            
        current_quantity, warehouse = result

        if change_type == 'out':
            quantity_change = -quantity_change
            if current_quantity + quantity_change < 0:
                conn.close()
                return jsonify({'success': False, 'message': '재고가 부족합니다.'})

        new_quantity = current_quantity + quantity_change
        korea_time = get_korea_time().strftime('%Y-%m-%d %H:%M:%S')

        cursor.execute('UPDATE inventory SET quantity = %s, last_modifier = %s, last_modified = %s WHERE id = %s',
                      (new_quantity, session['user_name'], korea_time, item_id))

        cursor.execute('INSERT INTO inventory_history (inventory_id, change_type, quantity_change, modifier_name, modified_at) VALUES (%s, %s, %s, %s, %s)',
                      (item_id, change_type, quantity_change, session['user_name'], korea_time))

        conn.commit()
        conn.close()

        return jsonify({'success': True, 'new_quantity': new_quantity})
        
    except Exception as e:
        return jsonify({'success': False, 'message': '수량 업데이트 중 오류가 발생했습니다.'})

@app.route('/upload_photo/<int:item_id>', methods=['POST'])
def upload_photo(item_id):
    """사진 업로드"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': '로그인이 필요합니다.'}), 401

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
            conn = get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute('INSERT INTO photos (inventory_id, filename, original_name, file_size, uploaded_by) VALUES (%s, %s, %s, %s, %s)',
                          (item_id, filename, file.filename, file_size, session['user_name']))
            
            conn.commit()
            conn.close()
            return jsonify({'success': True, 'message': '사진이 업로드되었습니다.'})
            
        except Exception as e:
            return jsonify({'success': False, 'message': '사진 업로드 중 오류가 발생했습니다.'})

    return jsonify({'success': False, 'message': '지원하지 않는 파일 형식입니다.'})

@app.route('/photos/<int:item_id>')
def view_photos(item_id):
    """사진 보기 페이지"""
    if 'user_id' not in session:
        return redirect('/')

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT id, filename, original_name, file_size, uploaded_by, uploaded_at FROM photos WHERE inventory_id = %s ORDER BY uploaded_at DESC', (item_id,))
        photos = cursor.fetchall()
        
        cursor.execute('SELECT part_name, warehouse, category FROM inventory WHERE id = %s', (item_id,))
        item_info = cursor.fetchone()
        conn.close()

        return render_template('photos.html', 
                             photos=photos, 
                             item_id=item_id, 
                             item_info=item_info,
                             is_admin=session.get('is_admin', False))
        
    except Exception as e:
        flash('사진 정보를 불러오는 중 오류가 발생했습니다.')
        if session.get('is_admin'):
            return redirect('/admin/warehouse')
        else:
            return redirect('/dashboard')

@app.route('/delete_photo/<int:photo_id>')
def delete_photo(photo_id):
    """사진 삭제 (관리자 전용)"""
    if 'user_id' not in session or not session.get('is_admin'):
        flash('관리자 권한이 필요합니다.')
        return redirect('/')

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT filename, inventory_id FROM photos WHERE id = %s', (photo_id,))
        photo_info = cursor.fetchone()
        
        if photo_info:
            filename, inventory_id = photo_info
            
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            if os.path.exists(file_path):
                os.remove(file_path)
            
            cursor.execute('DELETE FROM photos WHERE id = %s', (photo_id,))
            conn.commit()
            flash('사진이 삭제되었습니다.')
            conn.close()
            return redirect(f'/photos/{inventory_id}')
        else:
            flash('삭제할 사진을 찾을 수 없습니다.')
            conn.close()
        
    except Exception as e:
        flash('사진 삭제 중 오류가 발생했습니다.')
    
    if session.get('is_admin'):
        return redirect('/admin/warehouse')
    else:
        return redirect('/dashboard')

@app.route('/search_inventory')
def search_inventory():
    """재고 검색 페이지 - 무한 리디렉션 및 datetime 오류 해결"""
    if 'user_id' not in session:
        return redirect('/')
    
    query = request.args.get('q', '').strip()
    warehouse = request.args.get('warehouse', '')
    category = request.args.get('category', '')
    
    print(f"🔍 재고 검색 요청: query='{query}', warehouse='{warehouse}', category='{category}'")
    
    if not query and not warehouse and not category:
        # 빈 검색 결과 표시
        return render_template('search_results.html', 
                             inventory=[], 
                             query='',
                             warehouse='',
                             category='',
                             is_admin=session.get('is_admin', False))
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        where_conditions = []
        params = []
        
        if query:
            where_conditions.append("i.part_name LIKE %s")
            params.append(f'%{query}%')
        
        if warehouse:
            where_conditions.append("i.warehouse = %s")
            params.append(warehouse)
        
        if category:
            where_conditions.append("i.category = %s")
            params.append(category)
        
        where_clause = " AND ".join(where_conditions) if where_conditions else "1=1"
        
        query_sql = f'''SELECT i.id, i.warehouse, i.category, i.part_name, i.quantity, 
                              i.last_modifier, i.last_modified, COUNT(p.id) as photo_count
                       FROM inventory i
                       LEFT JOIN photos p ON i.id = p.inventory_id
                       WHERE {where_clause}
                       GROUP BY i.id, i.warehouse, i.category, i.part_name, i.quantity, i.last_modifier, i.last_modified
                       ORDER BY i.warehouse, i.category, i.part_name'''
        
        cursor.execute(query_sql, params)
        raw_inventory = cursor.fetchall()
        conn.close()
        
        # 🔧 날짜 형식 변환 처리 (datetime 오류 해결)
        inventory = []
        for item in raw_inventory:
            item_list = list(item)
            if item_list[6]:  # last_modified가 존재하면
                if isinstance(item_list[6], str):
                    # 이미 문자열이면 그대로 사용
                    pass
                else:
                    # datetime 객체면 문자열로 변환
                    item_list[6] = item_list[6].strftime('%Y-%m-%d %H:%M:%S')
            inventory.append(item_list)
        
        print(f"✅ 검색 결과: {len(inventory)}개 항목 발견")
        
        return render_template('search_results.html', 
                             inventory=inventory, 
                             query=query,
                             warehouse=warehouse,
                             category=category,
                             is_admin=session.get('is_admin', False))
        
    except Exception as e:
        print(f"❌ 검색 중 오류: {type(e).__name__}: {str(e)}")
        
        # 🔧 오류 발생 시 빈 결과와 함께 검색 페이지 표시 (리디렉션 방지)
        return render_template('search_results.html', 
                             inventory=[], 
                             query=query,
                             warehouse=warehouse,
                             category=category,
                             is_admin=session.get('is_admin', False),
                             error_message=f'검색 중 오류가 발생했습니다: {str(e)}')


@app.route('/delete_inventory/<int:item_id>')
def delete_inventory(item_id):
    """재고 삭제 (관리자 전용)"""
    if 'user_id' not in session or not session.get('is_admin'):
        flash('관리자 권한이 필요합니다.')
        return redirect('/')

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT filename FROM photos WHERE inventory_id = %s', (item_id,))
        photos = cursor.fetchall()
        
        for photo in photos:
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], photo[0])
            if os.path.exists(file_path):
                os.remove(file_path)
        
        cursor.execute('DELETE FROM photos WHERE inventory_id = %s', (item_id,))
        cursor.execute('DELETE FROM inventory_history WHERE inventory_id = %s', (item_id,))
        cursor.execute('SELECT warehouse, category FROM inventory WHERE id = %s', (item_id,))
        item_info = cursor.fetchone()
        cursor.execute('DELETE FROM inventory WHERE id = %s', (item_id,))
        
        conn.commit()
        conn.close()
        
        flash('재고 아이템이 삭제되었습니다.')
        
        if item_info:
            warehouse, category = item_info
            return redirect(f'/warehouse/{warehouse}/electric')
        
    except Exception as e:
        flash('재고 삭제 중 오류가 발생했습니다.')
    
    if session.get('is_admin'):
        return redirect('/admin/warehouse')
    else:
        return redirect('/dashboard')

@app.route('/logout')
def logout():
    """로그아웃"""
    session.clear()
    flash('로그아웃되었습니다.')
    return redirect('/')

@app.route('/api/inventory_stats')
def inventory_stats():
    """재고 통계 API"""
    if 'user_id' not in session:
        return jsonify({'error': '로그인이 필요합니다.'}), 401
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT COUNT(*) FROM inventory')
        total_items = cursor.fetchone()[0]
        
        cursor.execute('SELECT SUM(quantity) FROM inventory')
        total_quantity = cursor.fetchone()[0] or 0
        
        cursor.execute('SELECT warehouse, COUNT(*) FROM inventory GROUP BY warehouse')
        warehouse_stats = cursor.fetchall()
        
        cursor.execute('SELECT category, COUNT(*) FROM inventory GROUP BY category')
        category_stats = cursor.fetchall()
        
        conn.close()
        
        return jsonify({
            'total_items': total_items,
            'total_quantity': total_quantity,
            'warehouse_stats': dict(warehouse_stats),
            'category_stats': dict(category_stats)
        })
        
    except Exception as e:
        return jsonify({'error': '통계 조회 중 오류가 발생했습니다.'}), 500

@app.route('/health')
def health():
    """시스템 상태 확인 API"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT 1')
        conn.close()
        
        return jsonify({
            'status': 'healthy',
            'database': 'postgresql',
            'supabase_connected': True,
            'timestamp': datetime.now().isoformat(),
            'message': 'SK오앤에스 창고관리 시스템 (Supabase PostgreSQL) 정상 작동 중'
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'database': 'postgresql',
            'supabase_connected': False,
            'timestamp': datetime.now().isoformat(),
            'message': f'Supabase 연결 오류: {str(e)}'
        }), 500

@app.route('/inventory_history/<int:item_id>')
def inventory_history(item_id):
    """재고 이력 페이지"""
    if 'user_id' not in session:
        return redirect('/')

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 재고 이력 조회
        cursor.execute('''SELECT change_type, quantity_change, modifier_name, modified_at 
                         FROM inventory_history 
                         WHERE inventory_id = %s 
                         ORDER BY modified_at DESC''', (item_id,))
        history = cursor.fetchall()
        
        # 재고 정보 조회
        cursor.execute('SELECT part_name, warehouse, category, quantity FROM inventory WHERE id = %s', (item_id,))
        item_info = cursor.fetchone()
        
        conn.close()
        
        return render_template('inventory_history.html',
                             history=history,
                             item_info=item_info,
                             item_id=item_id)
        
    except Exception as e:
        flash('재고 이력을 불러오는 중 오류가 발생했습니다.')
        if session.get('is_admin'):
            return redirect('/admin/warehouse')
        else:
            return redirect('/dashboard')

@app.route('/export_inventory')
def export_inventory():
    """재고 데이터 내보내기 (관리자 전용)"""
    if 'user_id' not in session or not session.get('is_admin'):
        flash('관리자 권한이 필요합니다.')
        return redirect('/')
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''SELECT warehouse, category, part_name, quantity, last_modifier, last_modified 
                         FROM inventory 
                         ORDER BY warehouse, category, part_name''')
        inventory_data = cursor.fetchall()
        conn.close()
        
        # CSV 형태로 데이터 준비
        output = io.StringIO()
        writer = csv.writer(output)
        
        # 헤더 작성
        writer.writerow(['창고', '카테고리', '부품명', '수량', '최종수정자', '최종수정일'])
        
        # 데이터 작성
        for row in inventory_data:
            writer.writerow(row)
        
        # 파일 다운로드 응답
        response = Response(
            output.getvalue(),
            mimetype='text/csv',
            headers={'Content-Disposition': f'attachment; filename=inventory_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'}
        )
        
        return response
        
    except Exception as e:
        flash('데이터 내보내기 중 오류가 발생했습니다.')
        return redirect('/admin/dashboard')

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
    </body>
    </html>
    ''', 404

@app.errorhandler(500)
def internal_error(error):
    """500 에러 핸들러"""
    return '''
    <html>
    <head><title>500 - 서버 오류</title></head>
    <body style="font-family: Arial, sans-serif; text-align: center; padding: 50px;">
        <h1>500 - 서버 내부 오류</h1>
        <p>서버에서 문제가 발생했습니다.</p>
        <p>잠시 후 다시 시도해주세요.</p>
        <a href="/" style="color: #007bff; text-decoration: none;">홈으로 돌아가기</a>
    </body>
    </html>
    ''', 500

@app.errorhandler(403)
def forbidden(error):
    """403 에러 핸들러"""
    return '''
    <html>
    <head><title>403 - 접근 권한 없음</title></head>
    <body style="font-family: Arial, sans-serif; text-align: center; padding: 50px;">
        <h1>403 - 접근 권한이 없습니다</h1>
        <p>이 페이지에 접근할 권한이 없습니다.</p>
        <a href="/" style="color: #007bff; text-decoration: none;">홈으로 돌아가기</a>
    </body>
    </html>
    ''', 403

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


