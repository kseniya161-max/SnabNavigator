import streamlit as st
import pandas as pd
import re
from datetime import datetime

st.set_page_config(page_title="SnabNavigator", layout="wide")
st.title("SnabNavigator - Проверка условий договоров")

uploaded_files = st.file_uploader("Выберите файлы (TXT)", type=["txt"], accept_multiple_files=True)
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

    # 3. Извлекаем дату документа
    doc_date_match = re.search(r'Дата(?:\s+проекта)?:\s*(\d{2}\.\d{2}\.\d{4})', text)
    doc_date_str = f" от {doc_date_match.group(1)}" if doc_date_match else ""

    # 4. Тип и НОМЕР документа
    if "ДОПОЛНИТЕЛЬНОЕ СОГЛАШЕНИЕ" in text:
        doc_type = "Допсоглашение"
        doc_num_match = re.search(r'СОГЛАШЕНИЕ\s*№\s*(\d+)', text)
        doc_num = f" № {doc_num_match.group(1)}" if doc_num_match else ""
    elif "ПИСЬМО" in text:
        doc_type = "Письмо"
        doc_num = ""
    elif "ПРОЕКТ" in text:
        doc_type = "Проект допсоглашения"
        doc_num_match = re.search(r'СОГЛАШЕНИЯ\s*№\s*(\d+)', text)
        doc_num = f" № {doc_num_match.group(1)}" if doc_num_match else ""
    else:
        doc_type = "Договор"
        doc_num = ""

    # Собираем полное имя документа
    doc_full_name = f"{doc_type}{doc_num}{doc_date_str}"

    # 5. Сумма и цитата
    amount_match = re.search(r'Общая стоимость.*?составляет\s*[\d\s]+\s*\([^)]+\)\s*рублей', text)
    if amount_match:
        amount_quote = amount_match.group(0)
        amount = re.search(r'([\d\s]+)\s*\(', amount_quote).group(1).strip()
    else:
        amount_quote = "Нет данных"
        amount = "Нет данных"

    # 6. Срок и цитата
    date_match = re.search(r'не позднее\s*\d{2}\.\d{2}\.\d{4}', text)
    if date_match:
        date_quote = date_match.group(0)
        date = re.search(r'\d{2}\.\d{2}\.\d{4}', date_quote).group(0)
    else:
        date_quote = "Нет данных"
        date = "Нет данных"

    # 7. Поставщик (Ищем либо "Поставщик:", либо "От:")
    supplier_match = re.search(r'(?:Поставщик|От):\s*([^\n\.]+)', text)
    supplier = supplier_match.group(1).strip() if supplier_match else "Нет данных"

    return {
        "Номер": contract,
        "Тип документа": doc_type,
        "Полное_имя_документа": doc_full_name,
        "Статус": status,
        "Поставщик": supplier,
        "Сумма": amount,
        "Срок поставки": date,
        "Имя файла": filename,
        "Цитата_суммы": amount_quote,
        "Цитата_даты": date_quote,
        "Полный_текст": text
    }


if uploaded_files:
    all_docs = []
    for file in uploaded_files:
        text = file.read().decode("utf-8")
        all_docs.append(extract_info(text, file.name))

    main_contracts = {}
    review_docs = []

    for doc in all_docs:
        if doc["Тип документа"] in ["Письмо", "Проект допсоглашения"]:
            review_docs.append(doc)
        elif doc["Тип документа"] == "Допсоглашение" and doc["Статус"] == "Подписан":
            main_contracts[doc["Номер"]] = doc
        elif doc["Тип документа"] == "Договор":
            if doc["Номер"] not in main_contracts:
                main_contracts[doc["Номер"]] = doc

    # --- ГЛАВНАЯ ТАБЛИЦА ---
    st.subheader("Действующие условия на 10.03.2026")
    main_data = []
    for num, doc in main_contracts.items():
        if doc["Тип документа"] == "Допсоглашение":
            basis_text = f"Изменено: {doc['Полное_имя_документа']} (файл: {doc['Имя файла']})"
        else:
            basis_text = f"Без изменений: {doc['Полное_имя_документа']} (файл: {doc['Имя файла']})"

        main_data.append({
            "Номер договора": num,
            "Поставщик": doc["Поставщик"],
            "Сумма": doc["Сумма"],
            "Срок поставки": doc["Срок поставки"],
            "Основание": basis_text
        })

    df_main = pd.DataFrame(main_data)
    st.dataframe(df_main, use_container_width=True)

    # --- БЛОК ОСНОВАНИЙ (ЦИТАТЫ) ---
    st.markdown("### Проверка оснований (проверяемый источник)")
    for num, doc in main_contracts.items():
        with st.expander(f"Посмотреть основание для договора {num}"):
            st.write(f"Документ, установивший условия: {doc['Полное_имя_документа']} (Файл: {doc['Имя файла']})")
            st.info(f"Точная цитата (Сумма): {doc['Цитата_суммы']}")
            st.info(f"Точная цитата (Срок): {doc['Цитата_даты']}")
            st.write("Переход к абзацу исходного текста:")

            highlighted_text = doc['Полный_текст'].replace(doc['Цитата_суммы'], f"**{doc['Цитата_суммы']}**").replace(
                doc['Цитата_даты'], f"**{doc['Цитата_даты']}**")
            st.markdown(highlighted_text)

    # --- НА КОНТРОЛЕ ---
    if review_docs:
        st.subheader("На контроле (Несогласованные изменения)")
        review_data = []
        for d in review_docs:
            review_data.append({
                "Номер договора": d["Номер"],
                "Поставщик": d["Поставщик"],
                "Документ": d["Полное_имя_документа"],
                "Файл": d["Имя файла"],
                "Статус": "Не подписано"
            })
        st.dataframe(pd.DataFrame(review_data), use_container_width=True)

    # --- ОТВЕТЫ НА ВОПРОСЫ ---
    st.markdown("---")
    st.subheader("Ответы на вопросы закупщика")

    if "STN-101" in main_contracts:
        doc_101 = main_contracts['STN-101']
        st.success(
            f"1. Срок поставки по договору STN-101 на 10 марта 2026 года: {doc_101['Срок поставки']}. (Изменен документом: {doc_101['Полное_имя_документа']})")

    if "STN-102" in main_contracts:
        st.success(f"2. Сумма договора STN-102: {main_contracts['STN-102']['Сумма']} руб.")

    if "STN-103" in main_contracts:
        st.warning(f"3. Сумма договора STN-103: {main_contracts['STN-103']['Сумма']}.")

    check_april = datetime(2026, 4, 1)
    early_contracts = []
    for num, doc in main_contracts.items():
        if doc["Срок поставки"] != "Нет данных":
            d_date = datetime.strptime(doc["Срок поставки"], "%d.%m.%Y")
            if d_date < check_april:
                has_review = any(rev["Номер"] == num for rev in review_docs)
                text = f"{num} (срок {doc['Срок поставки']})"
                if has_review:
                    text += " - Есть несогласованное изменение срока"
                early_contracts.append(text)

    st.info(
        "4. По каким договорам поставка запланирована раньше 1 апреля 2026 года и есть ли несогласованные изменения: " + (
            "; ".join(early_contracts) if early_contracts else "Нет"))

else:
    st.info("Ожидание загрузки файлов...")