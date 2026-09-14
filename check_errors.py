"""Stable, actionable public errors. Never persist raw browser stderr or URLs."""
import re
import subprocess

ERRORS = {
    'LOGIN_REQUIRED': ('需要登录或完成验证', '点击本公司的官网，在内置浏览器中完成登录或验证码，再重试此公司。'),
    'PAGE_REDIRECT': ('官网跳转到了其他页面', '打开官网确认登录状态和招聘类别；确认已进入投递记录页后再重试。'),
    'BROWSER_OFFLINE': ('未连接到查询浏览器', '重新双击启动软件，保持内置浏览器打开，稍等几秒后重试。'),
    'PROFILE_ERROR': ('查询浏览器身份不可用', '重新启动内置浏览器；自定义 profile 的使用者请核对 sites.json 配置。'),
    'NETWORK_ERROR': ('招聘网站网络连接失败', '在内置浏览器中打开官网，检查网络连接；官网能正常打开后再重试。'),
    'TIMEOUT': ('本次页面读取超时', '检查官网是否可以正常加载；稍后重试此公司，无需重新查询已成功的公司。'),
    'PAGE_LOADING': ('投递页面尚未加载完成', '在官网确认页面已经加载完成，稍后重试；持续失败时检查网络。'),
    'SITE_CHANGED': ('无法识别官网投递区域', '确认招聘类别和记录页正确；持续失败可能是官网改版，请反馈公司名称和错误代码。'),
    'INVALID_RESPONSE': ('浏览器返回了无法识别的数据', '重启内置浏览器后重试；持续失败时请反馈错误代码和软件版本。'),
    'BROWSER_READ_ERROR': ('浏览器未能完成页面读取', '关闭官网弹窗或验证提示后重试；仍失败时重新启动内置浏览器。'),
    'CONFIG_ERROR': ('站点配置不完整或格式错误', '检查用户数据目录中的 sites.json，恢复该公司的示例配置后重试。'),
    'DEPENDENCY_MISSING': ('运行文件缺失或无法启动', '重新解压完整 Release 包，保留所有文件夹，不要只移动可执行文件。'),
    'UNKNOWN_ERROR': ('该公司的查询意外失败', '重试此公司；若持续失败，请反馈公司名称、软件版本和错误代码。'),
}


class CheckError(RuntimeError):
    def __init__(self, code, *, wait_for_page=False):
        self.code = code
        self.wait_for_page = wait_for_page
        super().__init__(ERRORS[code][0])


def cli_error(stderr):
    text = stderr.lower()
    if re.search(r'err_name_not_resolved|err_internet_disconnected|err_connection|enotfound|eai_again|net::err_|network error', text):
        return CheckError('NETWORK_ERROR')
    if re.search(r'timeout|timed out', text):
        return CheckError('TIMEOUT')
    if re.search(r'profile|context.*(?:offline|not found|disconnected)', text):
        return CheckError('PROFILE_ERROR')
    if re.search(r'extension.*(?:not connected|offline)|browser.*(?:not connected|connect)|bridge|econnrefused', text):
        return CheckError('BROWSER_OFFLINE')
    return CheckError('BROWSER_READ_ERROR')


def details(error):
    if isinstance(error, CheckError):
        code = error.code
    elif isinstance(error, subprocess.TimeoutExpired):
        code = 'TIMEOUT'
    elif isinstance(error, (FileNotFoundError, PermissionError)):
        code = 'DEPENDENCY_MISSING'
    elif isinstance(error, (ValueError, KeyError, TypeError)):
        code = 'INVALID_RESPONSE'
    else:
        code = 'UNKNOWN_ERROR'
    title, suggestion = ERRORS[code]
    return {'error_code': code, 'error': title, 'suggestion': suggestion}
