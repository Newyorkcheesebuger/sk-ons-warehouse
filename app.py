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
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')

    # 관리자 계정 생성
    admin_password = generate_password_hash('Onsn1103813!')
    c.execute('INSERT OR IGNORE INTO users (name, employee_id, team, password, is_approved) VALUES (?, ?, ?, ?, ?)',
              ('관리자', 'admin', '관리', admin_password, 1))

    # 창고 재고 테이블
    c.execute('''CREATE TABLE IF NOT EXISTS inventory
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  warehouse TEXT NOT NULL,
                  category TEXT NOT NULL,
                  part_name TEXT NOT NULL,
                  quantity INTEGER DEFAULT 0,
                  last_modifier TEXT,
                  last_modified TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')

    # 재고 변경 이력 테이블 (2주 데이터 보관용)
    c.execute('''CREATE TABLE IF NOT EXISTS inventory_history
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  inventory_id INTEGER,
                  change_type TEXT,
                  quantity_change INTEGER,
                  modifier_name TEXT,
                  modified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  FOREIGN KEY (inventory_id) REFERENCES inventory (id))''')

    # 사진 테이블
    c.execute('''CREATE TABLE IF NOT EXISTS photos
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  inventory_id INTEGER,
                  filename TEXT NOT NULL,
                  original_name TEXT NOT NULL,
                  file_size INTEGER,
                  uploaded_by TEXT,
                  uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  FOREIGN KEY (inventory_id) REFERENCES inventory (id))''')

    conn.commit()
    conn.close()


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

        # 사번 검증 (N + 7자리 숫자)
        if not employee_number.startswith('N') or len(employee_number) != 8:
            flash('사번은 N으로 시작하고 7자리 숫자여야 합니다.')
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
    employee_id = request.form['employee_id']
    password = request.form['password']

    print(f"DEBUG: 로그인 시도 - ID: {employee_id}")

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

    conn = sqlite3.connect('warehouse.db')
    c = conn.cursor()
    c.execute('INSERT INTO inventory (warehouse, category, part_name, quantity, last_modifier) VALUES (?, ?, ?, ?, ?)',
              (warehouse_name, category, part_name, quantity, session['user_name']))
    conn.commit()
    conn.close()

    return redirect(url_for('electric_inventory', warehouse_name=warehouse_name))


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

    # 재고 업데이트
    c.execute('UPDATE inventory SET quantity = ?, last_modifier = ?, last_modified = ? WHERE id = ?',
              (new_quantity, session['user_name'], datetime.now(), item_id))

    # 이력 저장
    c.execute(
        'INSERT INTO inventory_history (inventory_id, change_type, quantity_change, modifier_name) VALUES (?, ?, ?, ?)',
        (item_id, change_type, quantity_change, session['user_name']))

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


# app.py 마지막 부분만 수정 (나머지는 동일)

# app.py 맨 마지막 부분을 다음과 같이 완전히 교체하세요

if __name__ == '__main__':
    init_db()

    # Render.com 환경 변수 확인
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
