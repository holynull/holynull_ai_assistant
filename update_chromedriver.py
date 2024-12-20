import os
import subprocess
import requests
import json
from zipfile import ZipFile
from io import BytesIO

def get_chrome_version():
    """获取本地Chrome浏览器版本"""
    try:
        # MacOS上Chrome的默认位置
        cmd = ['/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', '--version']
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        output, error = process.communicate()
        if error:
            raise Exception(f"Error getting Chrome version: {error.decode()}")
        version = output.decode().strip().split()[-1]  # 获取版本号
        return '.'.join(version.split('.')[:3])  # 只返回主版本号 (例如: 119.0.0)
    except Exception as e:
        raise Exception(f"Failed to get Chrome version: {e}")

def get_chromedriver_url(version):
    """获取对应版本ChromeDriver的下载URL"""
    try:
        # 获取所有版本信息
        response = requests.get('https://googlechromelabs.github.io/chrome-for-testing/known-good-versions-with-downloads.json')
        data = response.json()
        
        # 查找匹配版本
        matching_versions = [v for v in data['versions'] if v['version'].startswith(version)]
        if not matching_versions:
            raise Exception(f"No matching ChromeDriver found for Chrome version {version}")
        
        # 获取最新匹配版本的下载URL
        latest_matching = matching_versions[-1]
        for download in latest_matching['downloads'].get('chromedriver', []):
            if download['platform'] == 'mac-x64':
                return download['url']
        
        raise Exception(f"No mac-x64 ChromeDriver found for version {version}")
    except Exception as e:
        raise Exception(f"Failed to get ChromeDriver URL: {e}")

def download_and_extract_chromedriver(url, target_dir):
    """下载并解压ChromeDriver"""
    try:
        # 创建目标目录
        os.makedirs(target_dir, exist_ok=True)
        
        # 下载文件
        response = requests.get(url)
        if response.status_code != 200:
            raise Exception(f"Failed to download ChromeDriver: HTTP {response.status_code}")
        
        # 解压文件
        with ZipFile(BytesIO(response.content)) as zip_file:
            # 获取zip文件中chromedriver的路径
            chromedriver_path = next(
                path for path in zip_file.namelist() 
                if path.endswith('chromedriver')
            )
            # 解压chromedriver文件
            with zip_file.open(chromedriver_path) as source, \
                 open(os.path.join(target_dir, 'chromedriver'), 'wb') as target:
                target.write(source.read())
        
        # 设置执行权限
        os.chmod(os.path.join(target_dir, 'chromedriver'), 0o755)
        print(f"ChromeDriver successfully updated in {target_dir}")
    except Exception as e:
        raise Exception(f"Failed to download and extract ChromeDriver: {e}")

def update_chromedriver():
    """主函数：更新ChromeDriver"""
    try:
        # 获取Chrome版本
        chrome_version = get_chrome_version()
        print(f"Detected Chrome version: {chrome_version}")
        
        # 获取下载URL
        download_url = get_chromedriver_url(chrome_version)
        print(f"Found matching ChromeDriver URL: {download_url}")
        
        # 下载并解压
        target_dir = 'chromedriver-mac-x64'
        download_and_extract_chromedriver(download_url, target_dir)
    except Exception as e:
        print(f"Error updating ChromeDriver: {e}")

if __name__ == '__main__':
    update_chromedriver()