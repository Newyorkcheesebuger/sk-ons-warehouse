# -*- coding: utf-8 -*-
"""
간단한 도메인 설정 매니저
hosts 파일을 자동으로 설정하거나 Flask 내에서 도메인을 처리합니다.
"""

import os
import sys
import socket
import platform
import subprocess


class DomainManager:
    def __init__(self):
        self.domain = 'storageborame.net'
        self.local_ip = self.get_local_ip()

    def get_local_ip(self):
        """로컬 IP 주소를 자동으로 가져옵니다."""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except:
            return "127.0.0.1"

    def is_admin(self):
        """관리자 권한이 있는지 확인합니다."""
        try:
            if platform.system() == 'Windows':
                import ctypes
                return ctypes.windll.shell32.IsUserAnAdmin()
            else:
                return os.geteuid() == 0
        except:
            return False

    def get_hosts_file_path(self):
        """운영체제별 hosts 파일 경로를 반환합니다."""
        if platform.system() == 'Windows':
            return r'C:\Windows\System32\drivers\etc\hosts'
        else:
            return '/etc/hosts'

    def backup_hosts_file(self):
        """hosts 파일을 백업합니다."""
        hosts_path = self.get_hosts_file_path()
        backup_path = hosts_path + '.backup'

        try:
            if os.path.exists(hosts_path) and not os.path.exists(backup_path):
                with open(hosts_path, 'r', encoding='utf-8', errors='ignore') as src:
                    with open(backup_path, 'w', encoding='utf-8') as dst:
                        dst.write(src.read())
                print(f"✅ hosts 파일 백업 완료: {backup_path}")
        except Exception as e:
            print(f"⚠️ 백업 실패: {e}")

    def check_domain_exists(self):
        """도메인이 이미 설정되어 있는지 확인합니다."""
        hosts_path = self.get_hosts_file_path()

        try:
            with open(hosts_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                return self.domain in content
        except:
            return False

    def add_domain_to_hosts(self):
        """hosts 파일에 도메인을 추가합니다."""
        if self.check_domain_exists():
            print(f"✅ {self.domain} 도메인이 이미 설정되어 있습니다.")
            return True

        if not self.is_admin():
            print("❌ 관리자 권한이 필요합니다.")
            return False

        hosts_path = self.get_hosts_file_path()

        try:
            # 백업 생성
            self.backup_hosts_file()

            # hosts 파일에 도메인 추가
            with open(hosts_path, 'a', encoding='utf-8') as f:
                f.write(f"\n# SK오앤에스 창고관리 시스템\n")
                f.write(f"127.0.0.1    {self.domain}\n")
                f.write(f"{self.local_ip}    {self.domain}\n")

            print(f"✅ {self.domain} 도메인이 hosts 파일에 추가되었습니다.")

            # DNS 캐시 새로고침
            self.flush_dns()
            return True

        except Exception as e:
            print(f"❌ hosts 파일 수정 실패: {e}")
            return False

    def flush_dns(self):
        """DNS 캐시를 새로고침합니다."""
        try:
            if platform.system() == 'Windows':
                subprocess.run(['ipconfig', '/flushdns'], check=True, capture_output=True)
                print("✅ Windows DNS 캐시 새로고침 완료")
            elif platform.system() == 'Darwin':  # macOS
                subprocess.run(['sudo', 'dscacheutil', '-flushcache'], check=True, capture_output=True)
                print("✅ macOS DNS 캐시 새로고침 완료")
            elif platform.system() == 'Linux':
                subprocess.run(['sudo', 'systemctl', 'restart', 'systemd-resolved'], check=True, capture_output=True)
                print("✅ Linux DNS 캐시 새로고침 완료")
        except:
            print("⚠️ DNS 캐시 새로고침은 수동으로 해주세요.")

    def remove_domain_from_hosts(self):
        """hosts 파일에서 도메인을 제거합니다."""
        if not self.is_admin():
            print("❌ 관리자 권한이 필요합니다.")
            return False

        hosts_path = self.get_hosts_file_path()

        try:
            with open(hosts_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()

            # 도메인 관련 라인 제거
            new_lines = []
            skip_next = False

            for line in lines:
                if "SK오앤에스 창고관리 시스템" in line:
                    skip_next = True
                    continue
                elif skip_next and self.domain in line:
                    continue
                else:
                    skip_next = False
                    new_lines.append(line)

            with open(hosts_path, 'w', encoding='utf-8') as f:
                f.writelines(new_lines)

            print(f"✅ {self.domain} 도메인이 hosts 파일에서 제거되었습니다.")
            self.flush_dns()
            return True

        except Exception as e:
            print(f"❌ hosts 파일 수정 실패: {e}")
            return False

    def run_as_admin(self):
        """현재 스크립트를 관리자 권한으로 다시 실행합니다."""
        if platform.system() == 'Windows':
            import ctypes
            if not ctypes.windll.shell32.IsUserAnAdmin():
                # 관리자 권한으로 재실행
                ctypes.windll.shell32.ShellExecuteW(
                    None, "runas", sys.executable, " ".join(sys.argv), None, 1
                )
                return True
        else:
            if os.geteuid() != 0:
                # sudo로 재실행
                args = ['sudo', sys.executable] + sys.argv
                os.execvp('sudo', args)
                return True
        return False

    def setup_domain_easy(self):
        """간편한 도메인 설정"""
        print("🌐 간편 도메인 설정을 시작합니다...")
        print(f"📍 설정할 도메인: {self.domain}")
        print(f"🖥️  컴퓨터 IP: {self.local_ip}")
        print()

        if self.check_domain_exists():
            print("✅ 도메인이 이미 설정되어 있습니다!")
            return True

        if not self.is_admin():
            print("🔐 관리자 권한이 필요합니다.")

            if platform.system() == 'Windows':
                print("📝 다음 방법 중 하나를 선택하세요:")
                print("1. 이 프로그램을 우클릭 → '관리자 권한으로 실행'")
                print("2. 아래 명령어를 관리자 명령 프롬프트에서 실행:")
                print(f"   python {__file__}")
            else:
                print("📝 다음 명령어로 실행하세요:")
                print(f"   sudo python {__file__}")

            choice = input("\n🤔 자동으로 관리자 권한으로 재실행하시겠습니까? (y/n): ").lower()
            if choice == 'y':
                return self.run_as_admin()
            else:
                return False

        return self.add_domain_to_hosts()


# 간편 사용을 위한 함수들
def setup_domain():
    """도메인을 간편하게 설정합니다."""
    manager = DomainManager()
    return manager.setup_domain_easy()


def remove_domain():
    """도메인을 제거합니다."""
    manager = DomainManager()
    return manager.remove_domain_from_hosts()


def check_domain():
    """도메인 설정 상태를 확인합니다."""
    manager = DomainManager()
    if manager.check_domain_exists():
        print(f"✅ {manager.domain} 도메인이 설정되어 있습니다.")
        print(f"🌐 접속 주소: http://{manager.domain}:5000")
    else:
        print(f"❌ {manager.domain} 도메인이 설정되어 있지 않습니다.")
    return manager.check_domain_exists()


if __name__ == '__main__':
    print("=" * 50)
    print("🌐 SK오앤에스 창고관리 시스템 - 도메인 설정")
    print("=" * 50)

    print("\n📋 메뉴를 선택하세요:")
    print("1. 도메인 설정 (storageborame.net)")
    print("2. 도메인 제거")
    print("3. 도메인 상태 확인")
    print("4. 종료")

    try:
        choice = input("\n선택 (1-4): ").strip()

        if choice == '1':
            setup_domain()
        elif choice == '2':
            remove_domain()
        elif choice == '3':
            check_domain()
        elif choice == '4':
            print("👋 프로그램을 종료합니다.")
        else:
            print("❌ 잘못된 선택입니다.")

    except KeyboardInterrupt:
        print("\n\n👋 프로그램을 종료합니다.")
    except Exception as e:
        print(f"❌ 오류가 발생했습니다: {e}")

    input("\n아무 키나 누르면 종료됩니다...")