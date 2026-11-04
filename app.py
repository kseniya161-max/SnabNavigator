import streamlit as st
import pandas as pd
import re
from datetime import datetime

st.set_page_config(page_title="SnabNavigator", layout="wide")
st.title("SnabNavigator - Проверка условий договоров")

uploaded_files = st.file_uploader("Выберите файлы (TXT)", type=["txt"], accept_multiple_files=True)

# Дата проверки из задания
CHECK_DATE = datetime(2026, 3, 10)


def extract_info(text, filename):
    # 1. Номер договора
    contract_match = re.search(r'(STN-\d+)', text)
    contract = contract_match.group(1) if contract_match else "Нет данных"

    # 2. Статус
    if "Статус: подписан" in text or "подписан обеими сторонами" in text.lower():
        status = "Подписан"
    elif "проект" in text.lower() and "не подписан" in text.lower():
        status = "Проект (не подписан)"
    elif "письмо" in text.lower():
        status = "Письмо (предложение)"
    else:
        status = "Требует проверки"

    # 3. Сумма
    amount_match = re.search(r'Общая стоимость.*?составляет\s*([\d\s]+)\s*\(', text)
    amount = amount_match.group(1).strip() if amount_match else "Нет данных"

    # 4. Срок поставки
    date_match = re.search(r'не позднее\s*(\d{2}\.\d{2}\.\d{4})', text)
    date = date_match.group(1) if date_match else "Нет данных"

    # 5. Поставщик
    supplier_match = re.search(r'Поставщик:\s*([^.]+)', text)
    supplier = supplier_match.group(1).strip() if supplier_match else "Нет данных"

    # 6. Тип документа (определяем по тексту)
    if "ДОПОЛНИТЕЛЬНОЕ СОГЛАШЕНИЕ" in text:
        doc_type = "Допсоглашение"
    elif "ПИСЬМО" in text:
        doc_type = "Письмо"
    elif "ПРОЕКТ" in text:
        doc_type = "Проект"
    else:
        doc_type = "Договор"

    return {
        "Номер": contract,
        "Тип документа": doc_type,
        "Статус": status,
        "Поставщик": supplier,
        "Сумма": amount,
        "Срок поставки": date,
        "Имя файла": filename
    }


if uploaded_files:
    all_docs = []

    # Шаг 1: Собираем все данные из файлов
    for file in uploaded_files:
        text = file.read().decode("utf-8")
        info = extract_info(text, file.name)
        all_docs.append(info)

    # Шаг 2: Бизнес-логика (собираем договоры)
    main_contracts = {}  # Сюда складываем действующие условия
    review_docs = []  # Сюда складываем письма и проекты

    for doc in all_docs:
        # Если это письмо или проект - отправляем в блок "На контроле"
        if doc["Тип документа"] in ["Письмо", "Проект"]:
            review_docs.append(doc)
        # Если это подписанное допсоглашение - оно ПЕРЕЗАПИСЫВАЕТ данные договора
        elif doc["Тип документа"] == "Допсоглашение" and doc["Статус"] == "Подписан":
            main_contracts[doc["Номер"]] = doc
        # Если это обычный договор - сохраняем его (если для него еще нет допсоглашения)
        elif doc["Тип документа"] == "Договор":
            if doc["Номер"] not in main_contracts:
                main_contracts[doc["Номер"]] = doc

    # Шаг 3: Выводим главную таблицу
    st.subheader("Действующие условия на 10.03.2026")
    main_data = []
    for num, doc in main_contracts.items():
        main_data.append({
            "Номер": num,
            "Поставщик": doc["Поставщик"],
            "Сумма": doc["Сумма"],
            "Срок поставки": doc["Срок поставки"],
            "Основание": f"{doc['Тип документа']} (файл: {doc['Имя файла']})"
        })

    df_main = pd.DataFrame(main_data)
    st.dataframe(df_main, use_container_width=True)

    # Шаг 4: Выводим блок "На контроле" (если там что-то есть)
    if review_docs:
        st.subheader("На контроле (Несогласованные изменения)")
        review_data = []
        for doc in review_docs:
            review_data.append({
                "Номер": doc["Номер"],
                "Тип документа": doc["Тип документа"],
                "Имя файла": doc["Имя файла"],
                "Внимание": "Не подписано / Предложение"
            })
        df_review = pd.DataFrame(review_data)
        st.dataframe(df_review, use_container_width=True)

        # --- БЛОК ОТВЕТОВ НА ВОПРОСЫ ---
        st.markdown("---")
        st.subheader("Ответы на вопросы закупщика")

        # Формируем ответы на основе данных из main_contracts
        st.write("**1. Какой срок поставки действует по договору STN-101 на 10 марта 2026 года?**")
        if "STN-101" in main_contracts:
            st.success(
                f"Ответ: {main_contracts['STN-101']['Срок поставки']} (согласно {main_contracts['STN-101']['Тип документа']})")
        else:
            st.error("Договор не найден")

        st.write("**2. Какова сумма договора STN-102?**")
        if "STN-102" in main_contracts:
            st.success(f"Ответ: {main_contracts['STN-102']['Сумма']} руб.")
        else:
            st.error("Договор не найден")

        st.write("**3. Какова сумма договора STN-103?**")
        if "STN-103" in main_contracts:
            st.warning(f"Ответ: {main_contracts['STN-103']['Сумма']} (требуется проверка/запрос спецификации)")
        else:
            st.error("Договор не найден")

        st.write("**4. По каким договорам поставка раньше 01.04.2026 и есть ли несогласованные изменения?**")
        check_april = datetime(2026, 4, 1)
        early_contracts = []

        for num, doc in main_contracts.items():
            if doc["Срок поставки"] != "Нет данных":
                # Переводим строку в дату
                d_date = datetime.strptime(doc["Срок поставки"], "%d.%m.%Y")
                if d_date < check_april:
                    # Проверяем, есть ли по этому договору несогласованные документы
                    has_review = any(rev["Номер"] == num for rev in review_docs)
                    text = f"{num} (срок {doc['Срок поставки']})"
                    if has_review:
                        text += " -  ЕСТЬ несогласованное изменение срока"
                    early_contracts.append(text)

        if early_contracts:
            for item in early_contracts:
                st.info(f"• {item}")
        else:
            st.success("Нет договоров с поставкой раньше 01.04.2026")

else:
    st.info("Ожидание загрузки файлов...")