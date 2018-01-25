#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = 'zkqiang'
__github__ = 'https://github.com/zkqiang'

"""
依赖 selenium 加快 12306 购票速度
运行后根据提示进行操作即可
如果需要邮箱通知，请运行前先修改全局变量的邮箱信息
"""

import time
import random
import traceback
import re
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException, TimeoutException, \
    WebDriverException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# webdriver的浏览器类型
WEB_DRIVER = 'Chrome'
# 是否使用抢票成功后的邮件通知
NOTIFICATION_EMAIL = False
# 发送邮箱地址
FROM_EMAIL = 'zkqiang@126.com'
# 发送邮箱密码
EMAIL_PASSWORD = '12345678'
# 接收邮箱地址
TO_EMAIL = 'zkqiang@126.com'
# 发件服务器地址
SMTP_SERVER = 'smtp.126.com'
# 抢票间隔区间，不要太低容易封IP
MIN_INTERVAL = 0.4
MAX_INTERVAL = 0.8


class TrainTicket(object):

    def __init__(self):
        self.browser = getattr(webdriver, WEB_DRIVER)()
        self.browser.implicitly_wait(10)
        self.browser.get('https://kyfw.12306.cn/otn/leftTicket/init')

    def login(self):
        """登录账号"""
        # 展开订单帮手
        show_more_button = self.browser.find_element_by_id('show_more')
        if 'down' in show_more_button.get_attribute('class'):
            show_more_button.click()
        # 点击乘车人的请选择按钮，用于触发登录框
        self.browser.find_element_by_xpath('//*[@id="setion_postion"]/span/a').click()
        # 判断登录框是否出现，不出现可能是不在售票时段
        try:
            WebDriverWait(self.browser, 10).until(
                EC.visibility_of_element_located((By.ID, 'username')))
        except TimeoutException:
            print('当前无法抢票，可能不在售票时段内')
            exit()
        print('请在网页进行登录')
        # 等待登录框消失
        WebDriverWait(self.browser, 600).until(
            EC.invisibility_of_element_located((By.ID, 'username')))
        # 判断是否登录成功，否则重新进行
        login_user = self.browser.find_element_by_id('login_user')
        if '/otn/login/init' in login_user.get_attribute('href'):
            return self.login()
        print("登录完成")

    def purchase(self):
        """提示补充筛选条件后开始抢票"""
        input('请在网页补充筛选条件(日期、乘车人、车次、席别等)，确认无误后按回车继续：')
        print('开始抢票，如需暂停请删除乘车人，除此之外请不要做其他网页操作')
        # 进入循环抢票
        self._cycle()

    def _cycle(self):
        """抢票循环"""
        try:
            # 展开订单帮手
            show_more_button = self.browser.find_element_by_id('show_more')
            if 'down' in show_more_button.get_attribute('class'):
                show_more_button.click()
            # 勾选自动提交按钮
            auto_submit = self.browser.find_element_by_id('autoSubmit')
            if not auto_submit.is_selected():
                auto_submit.click()

            # 定位所有查询出错界面
            query_errors = self.browser.find_elements_by_class_name('no-ticket')
            # 定位查询按钮
            query_button = self.browser.find_element_by_id('query_ticket')
            # 定位提交订单窗口
            submit_box = self.browser.find_element_by_id('orange_msg')
            # 定位中间的车次信息栏
            sear_result = self.browser.find_element_by_id('sear-result')

            # 循环点击查询并处理查询后的网页交互
            while True:
                # 点击查询按钮发出新的查询请求
                if '停止查询' in query_button.text:
                    query_button.click()
                    query_button.click()
                else:
                    query_button.click()

                # 判断是否添加了乘车人
                if not re.search(r'position:static;background:none', self.browser.page_source):
                    print('未添加乘车人，请修改筛选条件')
                    return self.purchase()

                # 等待车次信息加载出来
                time.sleep(0.1)
                WebDriverWait(self.browser, 15).until(EC.visibility_of(sear_result))

                # 判断查询后是否出现其他各种出错提示
                for each in query_errors:
                    if each.is_displayed():
                        print('查询出错，请修改筛选条件')
                        return self.purchase()

                # 判断是否出现订单提交窗口
                if submit_box.is_displayed():
                    print('查询到车次，正在提交订单')
                    # 等待提交窗口
                    WebDriverWait(self.browser, 15).until_not(EC.visibility_of(submit_box))
                    # 等待加载图片消失
                    WebDriverWait(self.browser, 10).until_not(EC.visibility_of(
                        self.browser.find_element_by_xpath('//div[@dhxbox="1"]')))
                    try:
                        # 获取订票失败的提示页面的按钮，如果存在点击，不存在则订票成功
                        self.browser.find_element_by_id('qr_closeTranforDialog_id').click()
                        print('抢票失败，继续循环')
                    except NoSuchElementException:
                        # DOM里存在支付按钮说明成功进入支付界面，抢票成功
                        WebDriverWait(self.browser, 20).until(
                            EC.presence_of_element_located((By.ID, 'payButton')))
                        print('抢票成功，请尽快在30分钟内支付')
                        # 判断邮件通知是否被打开
                        if NOTIFICATION_EMAIL:
                            self._notice_to_pay()

                # 循环点击查询按钮的随机间隔
                time.sleep(random.uniform(MIN_INTERVAL, MAX_INTERVAL))

        except (NoSuchElementException, TimeoutException, WebDriverException):
            # 出现异常后打印异常重新开始
            print('程序出现异常，具体如下：\n%s\n等待30秒后重试' % traceback.format_exc())
            time.sleep(30)
            return self._cycle()

    @staticmethod
    def _notice_to_pay():
        """抢票成功的邮件通知，可选功能"""
        import smtplib
        from email.header import Header
        from email.mime.text import MIMEText

        from_addr = FROM_EMAIL
        password = EMAIL_PASSWORD
        to_addr = TO_EMAIL
        smtp_server = SMTP_SERVER

        msg = MIMEText('<html><body><h3>抢票成功，请在30分钟内支付</h3>' +
                       '<a href="https://kyfw.12306.cn/otn/queryOrder/initNoComplete">'
                       '点击登录12306</a>' +
                       '</body></html>', 'html', 'utf-8')
        msg['Subject'] = Header('12306抢票成功，请尽快支付', 'utf-8').encode()

        server = smtplib.SMTP(smtp_server, 25)
        server.set_debuglevel(1)
        server.login(from_addr, password)
        server.sendmail(from_addr, [to_addr], msg.as_string())
        server.quit()
        print('支付通知邮件已发送')

    def run(self):
        print('正在进入12306，在出现下个提示前，请不要操作网页')
        self.login()
        self.purchase()


if __name__ == '__main__':
    ticket = TrainTicket()
    ticket.run()
