from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import os
import time
from datetime import datetime
import pytz

app = Flask(__name__)
app.secret_key = 'sk_ons_warehouse_secret_key_2025'

def get_korea_time():
    """한국시간(KST)을 반환합니다."""
    korea_tz = pytz.timezone('Asia/Seoul')
    return datetime.now(korea_tz)

def init_db():
    try:
        print("데이터베이스 초기화 시작...")
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

        # 창고 재고 테이블
        c.execute('''CREATE TABLE IF NOT EXISTS inventory
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      warehouse TEXT NOT NULL,
                      category TEXT NOT NULL,
                      part_name TEXT NOT NULL,
                      quantity INTEGER DEFAULT 0,
                      last_modifier TEXT,
                      last_modified TEXT DEFAULT (datetime('now', '+9 hours')))''')

        # 관리자 계정 생성
        admin_password = generate_password_hash('Onsn1103813!')
        c.execute('INSERT OR IGNORE INTO users (name, employee_id, team, password, is_approved) VALUES (?, ?, ?, ?, ?)',
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
            conn = sqlite3.connect('warehouse.db')
            c = conn.cursor()
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

        conn = sqlite3.connect('warehouse.db')
        c = conn.cursor()
        c.execute('SELECT id, name, employee_id, password, is_approved FROM users WHERE employee_id = ?', (employee_id,))
        user = c.fetchone()
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
        conn = sqlite3.connect('warehouse.db')
        c = conn.cursor()
        c.execute('SELECT id, name, employee_id, team, is_approved, created_at FROM users WHERE employee_id != ?', ('admin',))
        users = c.fetchall()
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
        conn = sqlite3.connect('warehouse.db')
        c = conn.cursor()
        c.execute('UPDATE users SET is_approved = 1 WHERE id = ?', (user_id,))
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
        conn = sqlite3.connect('warehouse.db')
        c = conn.cursor()
        c.execute('SELECT name, employee_id FROM users WHERE id = ? AND employee_id != "admin"', (user_id,))
        user = c.fetchone()
        
        if user:
            c.execute('DELETE FROM users WHERE id = ?', (user_id,))
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
        conn = sqlite3.connect('warehouse.db')
        c = conn.cursor()
        c.execute('''SELECT id, category, part_name, quantity, last_modifier, last_modified
                     FROM inventory 
                     WHERE warehouse = ? AND category = "전기차"
                     ORDER BY id''', (warehouse_name,))
        inventory = c.fetchall()
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
        conn = sqlite3.connect('warehouse.db')
        c = conn.cursor()
        c.execute('INSERT INTO inventory (warehouse, category, part_name, quantity, last_modifier, last_modified) VALUES (?, ?, ?, ?, ?, ?)',
                  (warehouse_name, category, part_name, quantity, session['user_name'], korea_time))
        conn.commit()
        conn.close()
        
    except Exception as e:
        flash('재고 추가 중 오류가 발생했습니다.')
    
    return redirect(url_for('electric_inventory', warehouse_name=warehouse_name))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

# 헬스체크 엔드포인트
@app.route('/health')
def health():
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'database': 'sqlite',
        'version': '2.0 - 기본기능',
        'message': 'SK오앤에스 창고관리 시스템 정상 작동 중'
    })

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

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    is_render = os.environ.get('RENDER') is not None
    
    if is_render:
        print("🚀 SK오앤에스 창고관리 시스템 (Render.com 배포)")
        print(f"🌐 포트 {port}에서 서비스 시작...")
        print("✅ 2단계: 기본 기능 버전")
        app.run(host='0.0.0.0', port=port, debug=False)
    else:
        print("🚀 SK오앤에스 창고관리 시스템 (로컬 개발)")
        app.run(debug=True, host='0.0.0.0', port=5000, threaded=True)
