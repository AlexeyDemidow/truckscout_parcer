import re
import shutil
import time
import random
import os
import json

from fake_useragent import UserAgent

from bs4 import BeautifulSoup

from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.common import NoSuchElementException
from selenium_stealth import stealth

import requests


def get_random_chrome_user_agent():
    user_agent = UserAgent(browsers='chrome', os='windows', platforms='pc')
    return user_agent.random


def get_chrome_driver():
    options = Options()
    options.add_argument("--disable-notifications")
    options.add_argument("--disable-popup-blocking")
    options.add_argument('--disable-gpu')
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument('--headless=new')
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('excludeSwitches', ['enable-logging'])
    options.add_experimental_option('useAutomationExtension', False)

    chromedriver = 'chromedriver.exe'
    service = ChromeService(executable_path=chromedriver)
    driver = webdriver.Chrome(options=options, service=service)

    stealth(
        driver,
        languages=["en-US", "en"],
        user_agent=get_random_chrome_user_agent(),
        vendor="Google Inc.",
        platform="Win32",
        webgl_vendor="Intel Inc.",
        renderer="Intel Iris OpenGL Engine",
        fix_hairline=True,
        run_on_insecure_origins=True
    )

    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        'source': '''
                delete window.cdc_adoQpoasnfa76pfcZLmcfl_Array;
                delete window.cdc_adoQpoasnfa76pfcZLmcfl_Promise;
                delete window.cdc_adoQpoasnfa76pfcZLmcfl_Symbol;
          '''
    })

    return driver


ads = []  # Список для хранения конечного результата

# Создание или перезапись директории для хранения данных
if not os.path.exists('data'):
    os.makedirs('data')
else:
    shutil.rmtree('data')
    os.mkdir('data')

link = "https://www.truckscout24.de/transporter/gebraucht/kuehl-iso-frischdienst/renault"  # Исходная ссылка

browser = get_chrome_driver()

while True:
    browser.get(link)
    time.sleep(1)

    # Ссылка следующей страницы
    link = browser.find_element(By.XPATH, '//*[@id="offer-list-pagination"]/div/div/div/ul/li[5]/a').get_attribute(
        'href')

    soup = BeautifulSoup(browser.page_source, 'html.parser')

    # Ссылки на страницы транспорта
    pages = soup.find_all('section', class_='shadow-sm grid-card grid-card-border')
    pages_list = []
    for page in pages:
        pages_list.append(page.find('a', class_='d-flex flex-column text-decoration-none mb-2').get('href'))

    browser.get('https://www.truckscout24.de' + random.choice(pages_list))
    time.sleep(1)

    # Подготовка к скачиванию фото транспорта
    open_images = browser.find_element(By.XPATH, '//*[@id="imageandplaceboxes"]/div/button')
    time.sleep(1)
    browser.execute_script("arguments[0].click();", open_images)
    time.sleep(1)

    # Для открытия информации о продавце для получения телефона
    try:
        element = browser.find_element(By.XPATH, '//*[@id="dealer"]/div/div[2]/div[4]/button[1]')
    except NoSuchElementException:
        element = browser.find_element(By.XPATH, '//*[@id="dealer"]/div/div[2]/div[3]/button[1]')
    browser.execute_script("arguments[0].click();", element)
    time.sleep(1)

    adv_info = BeautifulSoup(browser.page_source, 'html.parser')

    adv_id = browser.current_url.split('/')[-1]  # id объявления

    href = browser.current_url  # Ссылка на объявление

    # Название
    title_prefix = ['Kühl-/Iso-/Frischdienst',
                    'Kühlaufbauwagen',
                    'Kältetechnik / iso / Frischdienst',
                    'Kühl-/Tiefkühltransport',
                    'Kühlkoffer',
                    'Kühltransporter',
                    'Kühl-/Tiefkühltransport']
    title = re.sub(r'\s+', ' ', adv_info.find('h1', class_='fs-3 mb-0').get_text().strip())
    for p in title_prefix:
        title = title.replace(p, '')

    # Цена
    try:
        price = int(re.sub(r'\s+', '',
                           adv_info.find('div', class_='fs-5 max-content my-1 word-break fw-bold').get_text().replace(
                               '€', '').replace('.', '')))
    except AttributeError:
        price = 0

    # Описание
    description = re.sub(r'\s+', ' ', adv_info.find('div', class_='col beschreibung').get_text())

    # Телефон
    phone = re.sub(r'\s+', ' ', adv_info.find_all('li', class_='ps-1 list-unstyled')[-1].find('a').get_text())

    mileage = 0
    color = ""
    power = 0
    all_info = adv_info.find_all('dl', {"class": "d-flex flex-column flex-lg-row border-bottom my-2 p-0 pb-2"})

    for i in all_info:
        # Пробег
        if 'Kilometerstand:' in i.get_text():
            mileage = int(re.sub(r'\D+', '', i.get_text()))
        # Цвет
        if 'Farbe:' in i.get_text():
            color = re.sub(r'\s+', '', i.get_text()).removeprefix('Farbe:')
        # Мощность
        if 'Leistung:' in i.get_text():
            # Вместо int установлен float из-за наличия дробных чисел значений мощности в объявлениях
            power = float(i.get_text().removeprefix('Leistung:').strip().split()[0].replace(',', '.'))

    # Первые 3 фотографии
    images = adv_info.find('div', {"class": "keen-slider thumbnail py-2"}).find_all('img')
    image_url_list = []
    for image in images:
        image_url_list.append(str(image.get('src')).replace('nds', 'hdv'))

    for image_url in image_url_list[:3]:
        if not os.path.exists(f'data/{adv_id}'):
            os.makedirs(f'data/{adv_id}')
        response = requests.get(image_url, stream=True)
        image_path = os.path.join(f'data/{adv_id}/' + f'{re.sub(r'[.?=-]', '', image_url.split('/')[-1])}.jpg')
        with open(image_path, 'wb') as file:
            for chunk in response.iter_content(chunk_size=128):
                file.write(chunk)

    # Итоговый словарь
    adv_dict = {
        "id": adv_id,
        "href": href,
        "title": title,
        "price": price,
        "mileage": mileage,
        "color": color,
        "power": power,
        "description": description,
        "phone": phone
    }

    ads.append(adv_dict)

    if link.endswith('#'):
        break

with open(f'data/data.json', 'w', encoding='utf-8') as f:
    json.dump(ads, f, ensure_ascii=False, indent=4)

browser.quit()
