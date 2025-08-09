from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, send_file
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import sqlite3
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
    # 여러 URL을 시도해서 접속 가능한 것으로 열기
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
    try:
        print("데이터베이스 초기화 시작...")
        conn = sqlite3.connect('warehouse.db')
        c = conn.cursor()

        # 사용자 테이블 (한국시간 기본값 설정)
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

        # 창고 재고 테이블 (한국시간 기본값 설정)
        c.execute('''CREATE TABLE IF NOT EXISTS inventory
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      warehouse TEXT NOT NULL,
                      category TEXT NOT NULL,
                      part_name TEXT NOT NULL,
                      quantity INTEGER DEFAULT 0,
                      last_modifier TEXT,
                      last_modified TEXT DEFAULT (datetime('now', '+9 hours')))''')

        # 재고 변경 이력 테이블 (한국시간 기본값 설정)
        c.execute('''CREATE TABLE IF NOT EXISTS inventory_history
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      inventory_id INTEGER,
                      change_type TEXT,
                      quantity_change INTEGER,
                      modifier_name TEXT,
                      modified_at TEXT DEFAULT (datetime('now', '+9 hours')),
                      FOREIGN KEY (inventory_id) REFERENCES inventory (id))''')

        # 사진 테이블 (한국시간 기본값 설정)
        c.execute('''CREATE TABLE IF NOT EXISTS photos
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      inventory_id INTEGER,
                      filename TEXT NOT NULL,
                      original_name TEXT NOT NULL,
                      file_size INTEGER,
                      uploaded_by TEXT,
                      uploaded_at TEXT DEFAULT (datetime('now', '+9 hours')),
                      FOREIGN KEY (inventory_id) REFERENCES inventory (id))''')

        conn.commit()
        conn.close()
        print("데이터베이스 초기화 완료!")
        
    except Exception as e:
        print(f"데이터베이스 초기화 오류: {e}")


# 🔥 핵심: 앱 시작 시 즉시 데이터베이스 초기화
init_db()


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

        # 비밀번호 길이 검증 (8자리 이상)
        if len(password) < 8:
            flash('비밀번호는 8자리 이상이어야 합니다.')
            return render_template('register.html')

        # 사번 검증 - N이 없으면 자동으로 추가
        if not employee_number.startswith('N'):
            employee_number = 'N' + employee_number
            
        if len(employee_number) != 8:
            flash('사번은 7자리 숫자여야 합니다.')
            return render_template('register.html')

        try:
            int(employee_number[1:])  # N 뒤의 숫자 부분 검증
        except ValueError:
            flash('사번 형식이 올바르지 않습니다.')
            return render_template('register.html')

        conn = sqlite3.connect('warehouse.db')
        c = conn.cursor()

        # 중복 사번 확인
        c.execute('SELECT id FROM users WHERE employee_id = ?', (employee_number,))
        if c.fetchone():
            flash('이미 등록된 사번입니다.')
            conn.close()
            return render_template('register.html')

        hashed_password = generate_password_hash(password)
        c.execute('INSERT INTO users (name, employee_id, team, password) VALUES (?, ?, ?, ?)',
                  (name, employee_number, team, hashed_password))
        conn.commit()
        conn.close()

        flash('회원가입이 완료되었습니다. 관리자 승인 후 이용 가능합니다.')
        return redirect(url_for('index'))

    return render_template('register.html')


@app.route('/login', methods=['POST'])
def login():
    try:
        employee_id = request.form.get('employee_id', '')
        password = request.form.get('password', '')

        print(f"DEBUG: 로그인 시도 - ID: {employee_id}")

        # 입력값 검증
        if not employee_id or not password:
            flash('아이디와 비밀번호를 입력해주세요.')
            return redirect(url_for('index'))

        conn = sqlite3.connect('warehouse.db')
        c = conn.cursor()
        c.execute('SELECT id, name, employee_id, password, is_approved FROM users WHERE employee_id = ?', (employee_id,))
        user = c.fetchone()
        conn.close()

        if user and check_password_hash(user[3], password):
            if user[4] == 0:  # 승인되지 않은 사용자
                flash('관리자 승인 대기 중입니다.')
                return redirect(url_for('index'))

            # 세션 완전 초기화
            session.clear()

            # 새 세션 설정
            session['user_id'] = user[0]
            session['user_name'] = user[1]
            session['employee_id'] = user[2]
            session['is_admin'] = (employee_id == 'admin')
            session.permanent = True

            print(f"DEBUG: 세션 설정 완료")
            print(f"DEBUG: - user_id: {session['user_id']}")
            print(f"DEBUG: - user_name: {session['user_name']}")
            print(f"DEBUG: - employee_id: {session['employee_id']}")
            print(f"DEBUG: - is_admin: {session['is_admin']}")

            # 관리자와 일반 사용자 명확히 구분
            if session['is_admin']:
                print("DEBUG: 관리자 → admin_dashboard로 리다이렉트")
                return redirect(url_for('admin_dashboard'))
            else:
                print("DEBUG: 일반 사용자 → dashboard로 리다이렉트")
                return redirect(url_for('dashboard'))
        else:
            flash('아이디 또는 비밀번호가 잘못되었습니다.')
            return redirect(url_for('index'))
            
    except Exception as e:
        print(f"DEBUG: 로그인 중 오류 발생: {str(e)}")
        flash('로그인 중 오류가 발생했습니다. 다시 시도해주세요.')
        return redirect(url_for('index'))


@app.route('/dashboard')
def dashboard():
    print(f"DEBUG: dashboard 접근 시도")
    print(f"DEBUG: 세션 user_id: {session.get('user_id')}")
    print(f"DEBUG: 세션 is_admin: {session.get('is_admin')}")

    if 'user_id' not in session:
        print("DEBUG: 로그인하지 않은 사용자 - 인덱스로 리다이렉트")
        return redirect(url_for('index'))

    # 관리자가 일반 사용자 대시보드에 접근하는 것을 차단
    if session.get('is_admin') == True:
        print("DEBUG: 관리자가 일반 사용자 dashboard 접근 시도 - admin_dashboard로 강제 리다이렉트")
        return redirect(url_for('admin_dashboard'))

    print(f"DEBUG: 일반 사용자 dashboard 정상 접근 - {session.get('user_name')}")
    return render_template('dashboard.html')


@app.route('/admin_dashboard')
def admin_dashboard():
    print(f"DEBUG: admin_dashboard 접근 시도")
    print(f"DEBUG: 세션 user_id: {session.get('user_id')}")
    print(f"DEBUG: 세션 is_admin: {session.get('is_admin')}")

    if 'user_id' not in session:
        print("DEBUG: 로그인하지 않은 사용자")
        flash('로그인이 필요합니다.')
        return redirect(url_for('index'))

    if not session.get('is_admin'):
        print("DEBUG: 일반 사용자가 admin_dashboard 접근 시도 - 차단")
        flash('관리자 권한이 필요합니다.')
        return redirect(url_for('dashboard'))  # 일반 사용자는 일반 대시보드로

    print(f"DEBUG: 관리자 admin_dashboard 정상 접근 - {session.get('user_name')}")

    conn = sqlite3.connect('warehouse.db')
    c = conn.cursor()
    c.execute('SELECT id, name, employee_id, team, is_approved, created_at FROM users WHERE employee_id != "admin"')
    users = c.fetchall()
    conn.close()

    return render_template('admin_dashboard.html', users=users)


@app.route('/approve_user/<int:user_id>')
def approve_user(user_id):
    if 'user_id' not in session or not session.get('is_admin'):
        return redirect(url_for('index'))

    conn = sqlite3.connect('warehouse.db')
    c = conn.cursor()
    c.execute('UPDATE users SET is_approved = 1 WHERE id = ?', (user_id,))
    conn.commit()
    conn.close()

    flash('사용자가 승인되었습니다.')
    return redirect(url_for('admin_dashboard'))


@app.route('/delete_user/<int:user_id>')
def delete_user(user_id):
    print(f"DEBUG: 사용자 삭제 요청 - user_id: {user_id}")
    print(f"DEBUG: 현재 세션 - is_admin: {session.get('is_admin')}, user_id: {session.get('user_id')}")

    if 'user_id' not in session or not session.get('is_admin'):
        print("DEBUG: 권한 없음 - 인덱스로 리다이렉트")
        flash('관리자 권한이 필요합니다.')
        return redirect(url_for('index'))

    conn = sqlite3.connect('warehouse.db')
    c = conn.cursor()

    # 삭제할 사용자 정보 가져오기 (admin 계정은 삭제 불가)
    c.execute('SELECT name, employee_id FROM users WHERE id = ? AND employee_id != "admin"', (user_id,))
    user = c.fetchone()

    print(f"DEBUG: 삭제 대상 사용자: {user}")

    if user:
        # 사용자 삭제
        c.execute('DELETE FROM users WHERE id = ?', (user_id,))
        conn.commit()
        print(f"DEBUG: 사용자 삭제 완료 - {user[0]}({user[1]})")
        flash(f'사용자 {user[0]}({user[1]})가 삭제되었습니다.')
    else:
        print("DEBUG: 삭제할 수 없는 사용자")
        flash('삭제할 수 없는 사용자입니다.')

    conn.close()
    return redirect(url_for('admin_dashboard'))


@app.route('/warehouse/<warehouse_name>')
def warehouse(warehouse_name):
    if 'user_id' not in session:
        return redirect(url_for('index'))

    # 보라매창고만 활성화
    if warehouse_name != '보라매창고':
        return render_template('preparing.html', warehouse_name=warehouse_name)

    return render_template('warehouse.html', warehouse_name=warehouse_name)


@app.route('/warehouse/<warehouse_name>/electric')
def electric_inventory(warehouse_name):
    if 'user_id' not in session:
        return redirect(url_for('index'))

    if warehouse_name != '보라매창고':
        return render_template('preparing.html', warehouse_name=warehouse_name)

    conn = sqlite3.connect('warehouse.db')
    c = conn.cursor()
    c.execute('''SELECT i.id, i.category, i.part_name, i.quantity, i.last_modifier, i.last_modified,
                        COUNT(p.id) as photo_count
                 FROM inventory i
                 LEFT JOIN photos p ON i.id = p.inventory_id
                 WHERE i.warehouse = ? AND i.category = "전기차"
                 GROUP BY i.id
                 ORDER BY i.id''', (warehouse_name,))
    inventory = c.fetchall()
    conn.close()

    return render_template('electric_inventory.html',
                           warehouse_name=warehouse_name,
                           inventory=inventory,
                           is_admin=session.get('is_admin', False))


@app.route('/add_inventory_item', methods=['POST'])
def add_inventory_item():
    if 'user_id' not in session or not session.get('is_admin'):
        return redirect(url_for('index'))

    warehouse_name = request.form['warehouse_name']
    category = request.form['category']
    part_name = request.form['part_name']
    quantity = int(request.form['quantity'])

    # 한국시간으로 현재 시간 얻기
    korea_time = get_korea_time().strftime('%Y-%m-%d %H:%M:%S')

    conn = sqlite3.connect('warehouse.db')
    c = conn.cursor()
    c.execute('INSERT INTO inventory (warehouse, category, part_name, quantity, last_modifier, last_modified) VALUES (?, ?, ?, ?, ?, ?)',
              (warehouse_name, category, part_name, quantity, session['user_name'], korea_time))
    conn.commit()
    conn.close()

    return redirect(url_for('electric_inventory', warehouse_name=warehouse_name))


@app.route('/delete_inventory_item/<int:item_id>')
def delete_inventory_item(item_id):
    """재고 아이템 삭제 (관리자 전용)"""
    print(f"DEBUG: 재고 아이템 삭제 요청 - item_id: {item_id}")
    print(f"DEBUG: 현재 세션 - is_admin: {session.get('is_admin')}, user_id: {session.get('user_id')}")

    if 'user_id' not in session or not session.get('is_admin'):
        print("DEBUG: 권한 없음 - 관리자 권한 필요")
        flash('관리자 권한이 필요합니다.')
        return redirect(url_for('index'))

    try:
        conn = sqlite3.connect('warehouse.db')
        c = conn.cursor()

        # 삭제할 아이템 정보 가져오기
        c.execute('SELECT warehouse, category, part_name FROM inventory WHERE id = ?', (item_id,))
        item = c.fetchone()

        if item:
            warehouse_name, category, part_name = item
            
            # 먼저 관련 사진들 삭제
            c.execute('SELECT filename FROM photos WHERE inventory_id = ?', (item_id,))
            photos = c.fetchall()
            
            # 실제 사진 파일들 삭제
            for photo in photos:
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], photo[0])
                if os.path.exists(file_path):
                    try:
                        os.remove(file_path)
                        print(f"DEBUG: 사진 파일 삭제 완료 - {photo[0]}")
                    except Exception as e:
                        print(f"DEBUG: 사진 파일 삭제 실패 - {photo[0]}: {e}")
            
            # DB에서 사진 레코드 삭제
            c.execute('DELETE FROM photos WHERE inventory_id = ?', (item_id,))
            
            # 재고 이력 삭제
            c.execute('DELETE FROM inventory_history WHERE inventory_id = ?', (item_id,))
            
            # 재고 아이템 삭제
            c.execute('DELETE FROM inventory WHERE id = ?', (item_id,))
            
            conn.commit()
            print(f"DEBUG: 재고 아이템 삭제 완료 - {part_name} ({category})")
            flash(f'물품 "{part_name}"이(가) 삭제되었습니다.')
            
            # 삭제 후 해당 창고의 전기차 재고 페이지로 리다이렉트
            return redirect(url_for('electric_inventory', warehouse_name=warehouse_name))
            
        else:
            print("DEBUG: 삭제할 아이템을 찾을 수 없음")
            flash('삭제할 물품을 찾을 수 없습니다.')
            return redirect(url_for('dashboard'))

    except Exception as e:
        print(f"DEBUG: 재고 아이템 삭제 중 오류: {e}")
        flash('물품 삭제 중 오류가 발생했습니다.')
        return redirect(url_for('dashboard'))
    
    finally:
        if 'conn' in locals():
            conn.close()


@app.route('/edit_inventory_item/<int:item_id>', methods=['GET', 'POST'])
def edit_inventory_item(item_id):
    """재고 아이템 수정 (관리자 전용)"""
    if 'user_id' not in session or not session.get('is_admin'):
        flash('관리자 권한이 필요합니다.')
        return redirect(url_for('index'))

    conn = sqlite3.connect('warehouse.db')
    c = conn.cursor()

    if request.method == 'POST':
        # 수정 처리
        part_name = request.form['part_name']
        quantity = int(request.form['quantity'])
        
        try:
            # 한국시간으로 현재 시간 얻기
            korea_time = get_korea_time().strftime('%Y-%m-%d %H:%M:%S')
            
            # 아이템 정보 업데이트 (한국시간 사용)
            c.execute('UPDATE inventory SET part_name = ?, quantity = ?, last_modifier = ?, last_modified = ? WHERE id = ?',
                      (part_name, quantity, session['user_name'], korea_time, item_id))
            
            # 수정 이력 저장 (한국시간 사용)
            c.execute('INSERT INTO inventory_history (inventory_id, change_type, quantity_change, modifier_name, modified_at) VALUES (?, ?, ?, ?, ?)',
                      (item_id, 'edit', 0, session['user_name'], korea_time))
            
            conn.commit()
            flash(f'물품 "{part_name}"이(가) 수정되었습니다.')
            
            # 수정 후 원래 페이지로 돌아가기
            c.execute('SELECT warehouse FROM inventory WHERE id = ?', (item_id,))
            warehouse = c.fetchone()
            conn.close()
            
            if warehouse:
                return redirect(url_for('electric_inventory', warehouse_name=warehouse[0]))
            else:
                return redirect(url_for('dashboard'))
                
        except Exception as e:
            print(f"DEBUG: 재고 아이템 수정 중 오류: {e}")
            flash('물품 수정 중 오류가 발생했습니다.')
            conn.close()
            return redirect(url_for('dashboard'))
    
    else:
        # 수정 폼 표시
        c.execute('SELECT warehouse, category, part_name, quantity FROM inventory WHERE id = ?', (item_id,))
        item = c.fetchone()
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


@app.route('/update_quantity', methods=['POST'])
def update_quantity():
    if 'user_id' not in session:
        return redirect(url_for('index'))

    data = request.get_json()
    item_id = data['item_id']
    change_type = data['change_type']  # 'in' or 'out'
    quantity_change = int(data['quantity'])

    conn = sqlite3.connect('warehouse.db')
    c = conn.cursor()

    # 현재 수량 가져오기
    c.execute('SELECT quantity, warehouse FROM inventory WHERE id = ?', (item_id,))
    current_quantity, warehouse = c.fetchone()

    # 수량 변경
    if change_type == 'out':
        quantity_change = -quantity_change
        if current_quantity + quantity_change < 0:
            return jsonify({'success': False, 'message': '재고가 부족합니다.'})

    new_quantity = current_quantity + quantity_change

    # 한국시간으로 현재 시간 얻기
    korea_time = get_korea_time().strftime('%Y-%m-%d %H:%M:%S')

    # 재고 업데이트 (한국시간 사용)
    c.execute('UPDATE inventory SET quantity = ?, last_modifier = ?, last_modified = ? WHERE id = ?',
              (new_quantity, session['user_name'], korea_time, item_id))

    # 이력 저장 (한국시간 사용)
    c.execute(
        'INSERT INTO inventory_history (inventory_id, change_type, quantity_change, modifier_name, modified_at) VALUES (?, ?, ?, ?, ?)',
        (item_id, change_type, quantity_change, session['user_name'], korea_time))

    conn.commit()
    conn.close()

    return jsonify({'success': True, 'new_quantity': new_quantity})


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

        # 파일 크기 계산 (KB)
        file_size = os.path.getsize(file_path) // 1024

        conn = sqlite3.connect('warehouse.db')
        c = conn.cursor()
        c.execute(
            'INSERT INTO photos (inventory_id, filename, original_name, file_size, uploaded_by) VALUES (?, ?, ?, ?, ?)',
            (item_id, filename, file.filename, file_size, session['user_name']))
        conn.commit()
        conn.close()

        return jsonify({'success': True, 'message': '사진이 업로드되었습니다.'})

    return jsonify({'success': False, 'message': '지원하지 않는 파일 형식입니다.'})


@app.route('/photos/<int:item_id>')
def view_photos(item_id):
    if 'user_id' not in session:
        return redirect(url_for('index'))

    conn = sqlite3.connect('warehouse.db')
    c = conn.cursor()
    c.execute(
        'SELECT id, filename, original_name, file_size, uploaded_by, uploaded_at FROM photos WHERE inventory_id = ?',
        (item_id,))
    photos = c.fetchall()
    conn.close()

    return render_template('photos.html', photos=photos, item_id=item_id, is_admin=session.get('is_admin', False))


@app.route('/download_photo/<int:photo_id>')
def download_photo(photo_id):
    if 'user_id' not in session or not session.get('is_admin'):
        return redirect(url_for('index'))

    conn = sqlite3.connect('warehouse.db')
    c = conn.cursor()
    c.execute('SELECT filename, original_name FROM photos WHERE id = ?', (photo_id,))
    photo = c.fetchone()
    conn.close()

    if photo:
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], photo[0])
        return send_file(file_path, as_attachment=True, download_name=photo[1])

    flash('파일을 찾을 수 없습니다.')
    return redirect(request.referrer)


@app.route('/delete_photo/<int:photo_id>')
def delete_photo(photo_id):
    if 'user_id' not in session or not session.get('is_admin'):
        return redirect(url_for('index'))

    conn = sqlite3.connect('warehouse.db')
    c = conn.cursor()
    c.execute('SELECT filename, inventory_id FROM photos WHERE id = ?', (photo_id,))
    photo = c.fetchone()

    if photo:
        # 파일 삭제
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], photo[0])
        if os.path.exists(file_path):
            os.remove(file_path)

        # DB에서 삭제
        c.execute('DELETE FROM photos WHERE id = ?', (photo_id,))
        conn.commit()
        flash('사진이 삭제되었습니다.')

    conn.close()
    return redirect(request.referrer)


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))


# 에러 핸들러 추가
@app.errorhandler(500)
def internal_error(error):
    print(f"500 에러 발생: {error}")
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


# 디버깅을 위한 임시 라우트 (문제 해결 후 제거)
@app.route('/debug_create_test_user')
def debug_create_test_user():
    if 'user_id' not in session or not session.get('is_admin'):
        return "관리자만 접근 가능"

    conn = sqlite3.connect('warehouse.db')
    c = conn.cursor()

    # 테스트 사용자 생성
    test_password = generate_password_hash('testpass123')
    try:
        c.execute('INSERT INTO users (name, employee_id, team, password, is_approved) VALUES (?, ?, ?, ?, ?)',
                  ('테스트사용자', 'N9999999', '설비', test_password, 1))
        conn.commit()
        conn.close()
        return "테스트 사용자 생성 완료: N9999999 / testpass123"
    except:
        conn.close()
        return "테스트 사용자가 이미 존재합니다"


@app.route('/debug_sessions')
def debug_sessions():
    return f"현재 세션: {dict(session)}"


# 2주 이상 된 이력 데이터 정리 (주기적으로 실행)
def cleanup_old_history():
    conn = sqlite3.connect('warehouse.db')
    c = conn.cursor()
    two_weeks_ago = datetime.now() - timedelta(days=14)
    c.execute('DELETE FROM inventory_history WHERE modified_at < ?', (two_weeks_ago,))
    conn.commit()
    conn.close()


if __name__ == '__main__':
    # 배포 환경 확인
    port = int(os.environ.get('PORT', 5000))
    is_render = os.environ.get('RENDER') is not None
    
    if is_render:
        # Render.com 배포 환경
        print("🚀 SK오앤에스 창고관리 시스템 (Render.com 배포)")
        print(f"🌐 포트 {port}에서 서비스 시작...")
        print("✅ 외부 접속 가능한 URL로 서비스됩니다.")
        
        # Render 요구사항: 0.0.0.0 호스트, PORT 환경변수 사용, debug=False
        app.run(host='0.0.0.0', port=port, debug=False)
        
    else:
        # 로컬 개발 환경 (기존 코드)
        local_ip = get_local_ip()
        domain = 'storageborame.net'

        print("=" * 60)
        print("🚀 SK오앤에스 창고관리 시스템을 시작합니다!")
        print("=" * 60)
        print()
        print("📱 접속 방법:")
        print(f"   💻 PC: http://localhost:5000")
        print(f"   🌐 네트워크: http://{local_ip}:5000")
        print(f"   ✨ 커스텀 도메인: http://{domain}:5000")
        print()
        print("🔧 커스텀 도메인이 작동하지 않는다면:")
        print("   1. domain_manager.py를 실행하세요")
        print("   2. 또는 python domain_manager.py 명령어 실행")
        print()
        print("⏹️  종료하려면 Ctrl+C를 누르세요")
        print("=" * 60)

        # 3초 후 자동으로 브라우저 열기
        threading.Thread(target=open_browser, daemon=True).start()

        try:
            app.run(debug=True, host='0.0.0.0', port=5000, threaded=True)
        except KeyboardInterrupt:
            print("\n👋 시스템을 종료합니다. 감사합니다!")
        except Exception as e:
            print(f"\n❌ 오류가 발생했습니다: {e}")
            print("🔧 포트 5000이 사용 중일 수 있습니다. 다른 포트를 사용하려면 app.py를 수정하세요.")
