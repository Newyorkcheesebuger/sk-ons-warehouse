# -*- coding: utf-8 -*-
"""
SK오앤에스 창고관리 시스템 - 원클릭 실행
이 파일을 실행하면 모든 설정이 자동으로 완료됩니다.
"""

import os
import sys
import subprocess
import socket
import webbrowser
import time
import threading


def check_python_version():
    """Python 버전을 확인합니다."""
    if sys.version_info < (3, 6):
        print("❌ Python 3.6 이상이 필요합니다.")
        print(f"현재 버전: {sys.version}")
        return False
    return True


def install_packages():
    """필요한 패키지를 설치합니다."""
    packages = ['Flask==2.3.3', 'Werkzeug==2.3.7']

    print("📦 필요한 패키지를 확인하는 중...")

    try:
        import flask
        print("✅ Flask가 이미 설치되어 있습니다.")
        return True
    except ImportError:
        pass

    print("📦 Flask를 설치하는 중...")
    try:
        for package in packages:
            subprocess.check_call([sys.executable, '-m', 'pip', 'install', package])
        print("✅ 패키지 설치 완료!")
        return True
    except subprocess.CalledProcessError:
        print("❌ 패키지 설치 실패. 인터넷 연결을 확인하세요.")
        return False


def create_folders():
    """필요한 폴더를 생성합니다."""
    folders = ['templates', 'static', 'static/uploads']

    for folder in folders:
        if not os.path.exists(folder):
            os.makedirs(folder)
            print(f"📁 {folder} 폴더 생성")


def get_local_ip():
    """로컬 IP를 가져옵니다."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"


def check_domain_setup():
    """도메인 설정 상태를 확인합니다."""
    try:
        if os.name == 'nt':  # Windows
            hosts_path = r'C:\Windows\System32\drivers\etc\hosts'
        else:  # Mac/Linux
            hosts_path = '/etc/hosts'

        if os.path.exists(hosts_path):
            with open(hosts_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                return 'storageborame.net' in content
    except:
        pass
    return False


def setup_domain_prompt():
    """도메인 설정 안내"""
    if check_domain_setup():
        print("✅ storageborame.net 도메인이 설정되어 있습니다!")
        return True

    print("\n🌐 커스텀 도메인 설정")
    print("=" * 40)
    print("storageborame.net 도메인으로 접속하시겠습니까?")
    print("(설정하지 않으면 IP 주소로만 접속 가능합니다)")
    print()

    choice = input("도메인을 설정하시겠습니까? (y/n): ").lower().strip()

    if choice == 'y':
        print("\n🔧 도메인 설정을 위해 domain_manager.py를 실행합니다...")

        # domain_manager.py가 있으면 실행
        if os.path.exists('domain_manager.py'):
            try:
                subprocess.run([sys.executable, 'domain_manager.py'], check=True)
                return True
            except:
                print("❌ 도메인 설정 실패")
        else:
            print("⚠️ domain_manager.py 파일이 없습니다.")
            print("📝 수동 설정 방법:")
            print("1. 관리자 권한으로 메모장 실행")
            print("2. C:\\Windows\\System32\\drivers\\etc\\hosts 파일 열기")
            print("3. 파일 끝에 다음 줄 추가:")
            print("   127.0.0.1    storageborame.net")
            print(f"   {get_local_ip()}    storageborame.net")

    return False


def open_browser_delayed():
    """3초 후 브라우저를 엽니다."""
    time.sleep(3)

    local_ip = get_local_ip()
    domain_set = check_domain_setup()

    # 접속 가능한 URL 찾기
    urls = []
    if domain_set:
        urls.append("http://storageborame.net:5000")
    urls.extend([
        f"http://{local_ip}:5000",
        "http://localhost:5000"
    ])

    for url in urls:
        try:
            webbrowser.open(url)
            print(f"🌐 브라우저에서 {url} 을(를) 열었습니다.")
            break
        except:
            continue


def run_flask_app():
    """Flask 앱을 실행합니다."""
    print("\n🚀 웹 서버를 시작합니다...")

    # 브라우저 자동 열기 (3초 후)
    threading.Thread(target=open_browser_delayed, daemon=True).start()

    try:
        # app.py 실행
        subprocess.run([sys.executable, 'app.py'])
    except KeyboardInterrupt:
        print("\n👋 서버를 종료합니다.")
    except FileNotFoundError:
        print("❌ app.py 파일을 찾을 수 없습니다.")
        print("📁 app.py 파일이 같은 폴더에 있는지 확인하세요.")
    except Exception as e:
        print(f"❌ 서버 실행 오류: {e}")


def main():
    """메인 실행 함수"""
    print("=" * 60)
    print("🏗️  SK오앤에스 창고관리 시스템 - 자동 설정")
    print("=" * 60)
    print()

    # 1. Python 버전 확인
    if not check_python_version():
        input("아무 키나 누르면 종료됩니다...")
        return

    # 2. 필요한 폴더 생성
    create_folders()

    # 3. 패키지 설치
    if not install_packages():
        input("아무 키나 누르면 종료됩니다...")
        return

    # 4. 도메인 설정 확인/안내
    setup_domain_prompt()

    # 5. 접속 정보 표시
    local_ip = get_local_ip()
    domain_set = check_domain_setup()

    print("\n📋 접속 정보")
    print("=" * 30)
    print(f"💻 PC 접속: http://localhost:5000")
    print(f"📱 모바일 접속: http://{local_ip}:5000")

    if domain_set:
        print(f"✨ 커스텀 도메인: http://storageborame.net:5000")
    else:
        print(f"⚠️ 커스텀 도메인: 설정되지 않음")

    print()
    print("🔐 초기 관리자 계정:")
    print("   ID: admin")
    print("   (비밀번호는 config.py 파일 참조)")
    print()

    # 6. Flask 앱 실행
    run_flask_app()


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n👋 설정을 취소했습니다.")
    except Exception as e:
        print(f"❌ 오류가 발생했습니다: {e}")

    input("\n아무 키나 누르면 종료됩니다...")