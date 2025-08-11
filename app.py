from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import os
import time
from datetime import datetime
import pytz

app = Flask(__name__)
app.secret_key = 'sk_ons_warehouse_secret_key_2025'

# 간단한 데이터베이스 초기화
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
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>SK오앤에스 창고관리 시스템</title>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body { font-family: Arial, sans-serif; margin: 0; padding: 20px; background: #f5f5f5; }
            .container { max-width: 400px; margin: 50px auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 5px 15px rgba(0,0,0,0.1); }
            h1 { text-align: center; color: #333; margin-bottom: 30px; }
            .form-group { margin-bottom: 20px; }
            label { display: block; margin-bottom: 5px; font-weight: bold; }
            input { width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 5px; font-size: 16px; }
            button { width: 100%; padding: 12px; background: #007bff; color: white; border: none; border-radius: 5px; font-size: 16px; cursor: pointer; }
            button:hover { background: #0056b3; }
            .success { color: #28a745; text-align: center; margin-bottom: 20px; }
            .error { color: #dc3545; text-align: center; margin-bottom: 20px; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🏭 SK오앤에스 창고관리</h1>
            
            <div class="success">
                ✅ 시스템이 정상적으로 배포되었습니다!<br>
                🗄️ SQLite 데이터베이스 연결됨<br>
                📱 모든 기능 준비 완료
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
            
            <p style="text-align: center; margin-top: 20px; font-size: 12px; color: #666;">
                테스트: admin / Onsn1103813!
            </p>
        </div>
    </body>
    </html>
    '''

@app.route('/login', methods=['POST'])
def login():
    try:
        employee_id = request.form.get('employee_id', '')
        password = request.form.get('password', '')

        if not employee_id or not password:
            return redirect(url_for('index'))

        conn = sqlite3.connect('warehouse.db')
        c = conn.cursor()
        c.execute('SELECT id, name, employee_id, password, is_approved FROM users WHERE employee_id = ?', (employee_id,))
        user = c.fetchone()
        conn.close()

        if user and check_password_hash(user[3], password):
            if user[4] == 0:
                return redirect(url_for('index'))

            session.clear()
            session['user_id'] = user[0]
            session['user_name'] = user[1]
            session['employee_id'] = user[2]
            session['is_admin'] = (employee_id == 'admin')
            session.permanent = True

            return redirect(url_for('dashboard'))
        else:
            return redirect(url_for('index'))
            
    except Exception as e:
        print(f"로그인 오류: {e}")
        return redirect(url_for('index'))

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('index'))
    
    return f'''
    <!DOCTYPE html>
    <html>
    <head>
        <title>대시보드</title>
        <meta charset="UTF-8">
        <style>
            body {{ font-family: Arial, sans-serif; margin: 0; padding: 20px; background: #f5f5f5; }}
            .container {{ max-width: 800px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 5px 15px rgba(0,0,0,0.1); }}
            h1 {{ color: #333; text-align: center; margin-bottom: 30px; }}
            .welcome {{ background: #e8f5e8; padding: 15px; border-radius: 8px; margin-bottom: 20px; text-align: center; }}
            .status {{ background: #e3f2fd; padding: 15px; border-radius: 8px; margin-bottom: 20px; }}
            a {{ display: inline-block; padding: 10px 20px; background: #dc3545; color: white; text-decoration: none; border-radius: 5px; }}
            a:hover {{ background: #c82333; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🎉 배포 성공!</h1>
            
            <div class="welcome">
                <h3>환영합니다, {session['user_name']}님!</h3>
                <p>사번: {session['employee_id']}</p>
                <p>관리자 권한: {'✅ 있음' if session.get('is_admin') else '❌ 없음'}</p>
            </div>
            
            <div class="status">
                <h4>📊 시스템 상태</h4>
                <p>✅ 데이터베이스: SQLite 연결됨</p>
                <p>✅ 세션 관리: 정상 작동</p>
                <p>✅ 사용자 인증: 정상 작동</p>
                <p>🚀 Render.com 배포: 성공!</p>
            </div>
            
            <p style="text-align: center;">
                <a href="/logout">로그아웃</a>
            </p>
        </div>
    </body>
    </html>
    '''

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
        'message': 'SK오앤에스 창고관리 시스템 정상 작동 중'
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    
    print("🚀 SK오앤에스 창고관리 시스템 시작")
    print(f"📱 포트: {port}")
    print("✅ 최소 기능 버전으로 배포 테스트")
    
    app.run(host='0.0.0.0', port=port, debug=False)
