from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import os
import urllib.parse
import uuid
from datetime import datetime
import pytz
import sys

app = Flask(__name__)
app.secret_key = 'sk_ons_warehouse_secret_key_2025'
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

# 업로드 폴더 생성
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# 환경변수 확인
DATABASE_URL = os.environ.get('SUPABASE_DB_URL')

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

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_korea_time():
    korea_tz = pytz.timezone('Asia/Seoul')
    return datetime.now(korea_tz)

def get_db_connection():
    """pg8000 버전 호환성 문제 해결된 데이터베이스 연결 함수"""
    try:
        import pg8000
        parsed = urllib.parse.urlparse(DATABASE_URL)
        
        # pg8000 최신 버전에서는 autocommit 파라미터가 제거됨
        conn = pg8000.connect(
            host=parsed.hostname,
            port=parsed.port or 5432,
            user=parsed.username,
            password=parsed.password,
            database=parsed.path[1:] if parsed.path else 'postgres'
        )
        
        # 연결 후 autocommit 설정 (최신 방식)
        try:
            conn.autocommit = False
        except AttributeError:
            # autocommit 속성이 없는 구버전의 경우 무시
            pass
        
        return conn
    except ImportError:
        print("❌ 치명적 오류: pg8000 라이브러리가 설치되지 않았습니다!")
        raise Exception("pg8000 라이브러리 필요")
    except Exception as e:
        print(f"❌ 치명적 오류: Supabase PostgreSQL 연결 실패!")
        print(f"   오류 내용: {e}")
        raise Exception(f"Supabase 연결 실패: {e}")

def check_db_health():
    """데이터베이스 상태 확인"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 테이블 존재 확인
        cursor.execute("""
            SELECT table_name FROM information_schema.tables 
            WHERE table_schema = 'public' AND table_name IN ('users', 'inventory', 'inventory_history', 'photos')
        """)
        tables = [row[0] for row in cursor.fetchall()]
        
        conn.close()
        return len(tables) == 4
    except:
        return False

def init_db():
    """pg8000 호환성 문제 해결된 데이터베이스 초기화 함수"""
    try:
        print("🔄 Supabase PostgreSQL 연결 테스트 중...")
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT version()')
        version_info = cursor.fetchone()[0]
        print(f"✅ Supabase 연결 성공!")
        print(f"📊 PostgreSQL 버전: {version_info[:50]}...")
        
        print("🔄 데이터베이스 테이블 생성 중...")
        
        # 단계 1: 테이블 생성
        try:
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
            
            # 재고 테이블
            cursor.execute('''CREATE TABLE IF NOT EXISTS inventory (
                id SERIAL PRIMARY KEY,
                warehouse TEXT NOT NULL,
                category TEXT NOT NULL,
                part_name TEXT NOT NULL,
                quantity INTEGER DEFAULT 0,
                last_modifier TEXT,
                last_modified TIMESTAMP DEFAULT (NOW() AT TIME ZONE 'Asia/Seoul')
            )''')
            
            # 재고 이력 테이블
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
            
            # 테이블 생성 커밋
            conn.commit()
            print("✅ 테이블 생성 완료")
            
        except Exception as table_error:
            conn.rollback()
            print(f"⚠️ 테이블 생성 중 오류 (무시하고 계속): {table_error}")
        
        # 단계 2: 관리자 계정 생성
        try:
            # 관리자 계정 존재 확인
            cursor.execute('SELECT id FROM users WHERE employee_id = %s', ('admin',))
            admin_exists = cursor.fetchone()
            
            if not admin_exists:
                admin_password = generate_password_hash('Onsn1103813!')
                cursor.execute('''INSERT INTO users (name, employee_id, team, password, is_approved) 
                                 VALUES (%s, %s, %s, %s, %s)''',
                              ('관리자', 'admin', '관리', admin_password, 1))
                conn.commit()
                print("✅ 관리자 계정 생성 완료")
            else:
                print("ℹ️ 관리자 계정 이미 존재")
                
        except Exception as admin_error:
            conn.rollback()
            print(f"⚠️ 관리자 계정 처리 중 오류 (무시하고 계속): {admin_error}")
        
        # 연결 종료
        conn.close()
        print("✅ Supabase 데이터베이스 초기화 완료!")
        print("💾 데이터 영구 보존 활성화")
        
        # 최종 상태 확인
        if check_db_health():
            print("🎯 데이터베이스 상태: 정상")
        else:
            print("⚠️ 데이터베이스 상태: 일부 테이블 누락 (계속 진행)")
        
    except Exception as e:
        print(f"❌ 치명적 오류: Supabase 초기화 실패!")
        print(f"   오류 내용: {e}")
        print("💡 트러블슈팅:")
        print("   1. pg8000 라이브러리 버전 확인")
        print("   2. SUPABASE_DB_URL 환경변수 확인")
        print("   3. Supabase 프로젝트 상태 확인")
        print("=" * 60)
        sys.exit(1)

# 시스템 시작 시 Supabase 연결 필수 확인
print("🔍 Supabase 연결 상태 확인 중...")
init_db()
print("=" * 60)
print("✅ 시스템 준비 완료 - Supabase 연결됨")
print("=" * 60)

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

        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT id, name, employee_id, password, is_approved FROM users WHERE employee_id = %s', (employee_id,))
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
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT id, name, employee_id, team, is_approved, created_at FROM users WHERE employee_id != %s', ('admin',))
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
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('UPDATE users SET is_approved = %s WHERE id = %s', (1, user_id))
        conn.commit()
        conn.close()
        flash('사용자가 승인되었습니다.')
        
    except Exception as e:
        flash('사용자 승인 중 오류가 발생했습니다.')
    
    return redirect(url_for('admin_dashboard'))

@app.route('/delete_user/<int:user_id>')
def delete_user(user_id):
    if 'user_id' not in session or not session.get('is_admin'):
        flash('관리자 권한이 필요합니다.')
        return redirect(url_for('index'))

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
    
    return redirect(url_for('admin_dashboard'))

@app.route('/warehouse/<warehouse_name>')
def warehouse(warehouse_name):
    if 'user_id' not in session:
        return redirect(url_for('index'))

    if warehouse_name not in ['보라매창고', '판교창고', '반포창고', '천안창고']:
        return render_template('preparing.html', warehouse_name=warehouse_name)

    return render_template('warehouse.html', warehouse_name=warehouse_name)

@app.route('/warehouse/<warehouse_name>/electric')
def electric_inventory(warehouse_name):
    if 'user_id' not in session:
        return redirect(url_for('index'))

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
        
        inventory = cursor.fetchall()
        conn.close()
        
        return render_template('electric_inventory.html',
                               warehouse_name=warehouse_name,
                               inventory=inventory,
                               is_admin=session.get('is_admin', False))
                               
    except Exception as e:
        flash('재고 정보를 불러오는 중 오류가 발생했습니다.')
        return redirect(url_for('dashboard'))

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
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('INSERT INTO inventory (warehouse, category, part_name, quantity, last_modifier, last_modified) VALUES (%s, %s, %s, %s, %s, %s)',
                      (warehouse_name, category, part_name, quantity, session['user_name'], korea_time))
        
        conn.commit()
        conn.close()
        
    except Exception as e:
        flash('재고 추가 중 오류가 발생했습니다.')
    
    return redirect(url_for('electric_inventory', warehouse_name=warehouse_name))

@app.route('/update_quantity', methods=['POST'])
def update_quantity():
    if 'user_id' not in session:
        return redirect(url_for('index'))

    data = request.get_json()
    item_id = data['item_id']
    change_type = data['change_type']
    quantity_change = int(data['quantity'])

    try:
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
    if 'user_id' not in session:
        return redirect(url_for('index'))

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
        return redirect(url_for('dashboard'))

@app.route('/delete_photo/<int:photo_id>')
def delete_photo(photo_id):
    if 'user_id' not in session or not session.get('is_admin'):
        flash('관리자 권한이 필요합니다.')
        return redirect(url_for('index'))

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
            return redirect(url_for('view_photos', item_id=inventory_id))
        else:
            flash('삭제할 사진을 찾을 수 없습니다.')
            conn.close()
        
    except Exception as e:
        flash('사진 삭제 중 오류가 발생했습니다.')
    
    return redirect(url_for('dashboard'))

@app.route('/search_inventory')
def search_inventory():
    if 'user_id' not in session:
        return redirect(url_for('index'))
    
    query = request.args.get('q', '').strip()
    warehouse = request.args.get('warehouse', '')
    category = request.args.get('category', '')
    
    if not query and not warehouse and not category:
        return render_template('search_results.html', inventory=[], query='')
    
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
        inventory = cursor.fetchall()
        conn.close()
        
        return render_template('search_results.html', 
                             inventory=inventory, 
                             query=query,
                             warehouse=warehouse,
                             category=category,
                             is_admin=session.get('is_admin', False))
        
    except Exception as e:
        flash('검색 중 오류가 발생했습니다.')
        return redirect(url_for('dashboard'))

@app.route('/delete_inventory/<int:item_id>')
def delete_inventory(item_id):
    if 'user_id' not in session or not session.get('is_admin'):
        flash('관리자 권한이 필요합니다.')
        return redirect(url_for('index'))

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
            return redirect(url_for('electric_inventory', warehouse_name=warehouse))
        
    except Exception as e:
        flash('재고 삭제 중 오류가 발생했습니다.')
    
    return redirect(url_for('dashboard'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/api/inventory_stats')
def inventory_stats():
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
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT 1')
        conn.close()
        
        db_healthy = check_db_health()
        
        return jsonify({
            'status': 'healthy' if db_healthy else 'warning',
            'database': 'postgresql',
            'supabase_connected': True,
            'all_tables_exist': db_healthy,
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

@app.errorhandler(500)
def internal_error(error):
    return '''
    <html>
    <head><title>서버 오류</title></head>
    <body>
        <h1>서버 내부 오류</h1>
        <p>Supabase 연결 문제가 발생했습니다.</p>
        <p><a href="/">홈으로 돌아가기</a></p>
        <p>관리자에게 문의하세요: 시스템 오류 발생</p>
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

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    is_render = os.environ.get('RENDER') is not None
    
    print("🎯 최종 시스템 정보:")
    print(f"📱 포트: {port}")
    print(f"🗄️ 데이터베이스: PostgreSQL (Supabase 전용)")
    print(f"🔒 보안: pg8000 호환성 문제 해결됨")
    print(f"🌐 환경: {'Production (Render)' if is_render else 'Development'}")
    print(f"💾 데이터 보존: 영구 (Supabase)")
    print("=" * 60)
    print("✅ 시스템 시작 - Supabase 연결 필수")
    print("=" * 60)
    
    app.run(host='0.0.0.0', port=port, debug=not is_render)
