import json
import datetime
from typing import Any, Dict
import redis
from driver import AtolDriver, AtolDriverError
from libfptr10 import IFptr
from settings import settings
from logger import logger


class CommandProcessor:
    """Процессор команд для ККТ с использованием паттерна инкапсуляции"""

    def __init__(self, redis_client=None):
        """Инициализация процессора с драйвером ККТ"""
        self.driver = AtolDriver()
        self.fptr = self.driver.fptr
        self.redis_client = redis_client

    def _get_cashier(self, device_id: str, kwargs: dict) -> tuple[str, str]:
        """
        Получить данные кассира с приоритетом:
        1. Из параметров запроса (kwargs)
        2. Из Redis (динамически установленный)
        3. Из настроек (settings)

        Returns:
            tuple[str, str]: (cashier_name, cashier_inn)
        """
        # Приоритет 1: из параметров запроса
        if 'cashier_name' in kwargs:
            cashier_name = kwargs.get('cashier_name')
            cashier_inn = kwargs.get('cashier_inn', '')
            if cashier_name:  # Если передано не пустое значение
                return cashier_name, cashier_inn

        # Приоритет 2: из Redis
        if self.redis_client:
            try:
                cashier_key = f"cashier:{device_id}"
                cashier_data = self.redis_client.hgetall(cashier_key)
                if cashier_data:
                    cashier_name = cashier_data.get(b"cashier_name", b"").decode('utf-8')
                    cashier_inn = cashier_data.get(b"cashier_inn", b"").decode('utf-8')
                    if cashier_name:
                        return cashier_name, cashier_inn
            except Exception as e:
                logger.warning(f"Ошибка при получении кассира из Redis: {e}")

        # Приоритет 3: из настроек
        return settings.cashier_name, settings.cashier_inn

    def _check_result(self, result: int, operation: str):
        """Проверяет результат выполнения операции драйвера"""
        if result < 0:
            error_description = self.fptr.errorDescription()
            error_code = self.fptr.errorCode()
            raise AtolDriverError(f"Ошибка {operation}: {error_description}", error_code=error_code)

    def _play_beep(self, frequency: int = 2000, duration: int = 100):
        """
        Воспроизвести звуковой сигнал

        Args:
            frequency: Частота в Гц
            duration: Длительность в мс
        """
        self.fptr.setParam(IFptr.LIBFPTR_PARAM_FREQUENCY, frequency)
        self.fptr.setParam(IFptr.LIBFPTR_PARAM_DURATION, duration)
        self._check_result(self.fptr.beep(), "подачи звукового сигнала")

    def _play_arcane_melody(self):
        """
        Сыграть мелодию "Enemy" из Arcane (Imagine Dragons feat. JID)

        🎵 I wake up to the sounds of the silence that allows... 🎵
        """
        logger.info("🎵 Начинаем проигрывать 'Enemy' из Arcane!")

        # Упрощённая мелодия "Enemy" - главная тема
        # Формат: (частота в Гц, длительность в мс)
        melody = [
            # "Look out for yourself"
            (392, 200),  # G4
            (392, 200),  # G4
            (440, 300),  # A4
            (392, 200),  # G4
            (100, 150),  # Пауза

            # "I wake up to the sounds"
            (349, 200),  # F4
            (392, 200),  # G4
            (440, 200),  # A4
            (494, 400),  # B4
            (100, 150),  # Пауза

            # "Of the silence that allows"
            (523, 250),  # C5
            (494, 250),  # B4
            (440, 250),  # A4
            (392, 400),  # G4
            (100, 200),  # Пауза

            # "For my mind to run around"
            (440, 200),  # A4
            (392, 200),  # G4
            (349, 200),  # F4
            (392, 200),  # G4
            (440, 400),  # A4
            (100, 150),  # Пауза

            # "With my ear up to the ground"
            (523, 300),  # C5
            (494, 200),  # B4
            (440, 200),  # A4
            (392, 500),  # G4
            (100, 200),  # Пауза

            # Припев: "Everybody wants to be my enemy"
            (392, 150),  # G4
            (392, 150),  # G4
            (440, 150),  # A4
            (440, 150),  # A4
            (494, 300),  # B4
            (523, 300),  # C5
            (100, 100),  # Пауза

            (523, 200),  # C5
            (494, 200),  # B4
            (440, 200),  # A4
            (392, 400),  # G4
            (100, 150),  # Пауза

            # "Spare the sympathy"
            (349, 200),  # F4
            (392, 200),  # G4
            (440, 300),  # A4
            (494, 500),  # B4
            (100, 200),  # Пауза

            # "Everybody wants to be"
            (523, 200),  # C5
            (523, 200),  # C5
            (494, 200),  # B4
            (440, 200),  # A4
            (392, 400),  # G4
            (100, 150),  # Пауза

            # "My enemy-y-y-y-y"
            (587, 250),  # D5
            (523, 250),  # C5
            (494, 250),  # B4
            (440, 250),  # A4
            (392, 600),  # G4
            (100, 200),  # Пауза

            # Финальный аккорд
            (392, 800),  # G4
        ]

        try:
            for frequency, duration in melody:
                self._play_beep(frequency, duration)

            logger.info("🎵 Мелодия 'Enemy' завершена! ⚔️")
            return True

        except Exception as e:
            logger.error(f"Ошибка проигрывания мелодии: {e}")
            raise AtolDriverError(f"Не удалось сыграть мелодию: {e}")

    def process_command(self, command_data: Dict[str, Any]) -> Dict[str, Any]:
        """Выполнение команды на основе полученной из pubsub"""
        response = {
            "command_id": command_data.get('command_id'),
            "success": False,
            "message": None,
            "data": None,
        }
        command = command_data.get('command')
        kwargs = command_data.get('kwargs', {})
        device_id = command_data.get('device_id', 'default')

        try:
            # ======================================================================
            # Connection Commands
            # ======================================================================
            if command == 'connection_open':
                if 'settings' in kwargs and kwargs['settings'] is not None:
                    self.fptr.setSettings(json.dumps(kwargs['settings']))
                self._check_result(self.fptr.open(), "открытия соединения")
                response['success'] = True
                response['message'] = "Соединение с ККТ успешно установлено"

            elif command == 'connection_close':
                self._check_result(self.fptr.close(), "закрытия соединения")
                response['success'] = True
                response['message'] = "Соединение с ККТ закрыто"

            elif command == 'connection_is_opened':
                is_opened = self.fptr.isOpened()
                response['success'] = True
                response['message'] = "Соединение активно" if is_opened else "Соединение не установлено"
                response['data'] = {
                    'is_opened': is_opened,
                    'message': response['message']
                }

            # ======================================================================
            # Shift Commands
            # ======================================================================
            elif command == 'shift_open':
                # Получение кассира с приоритетом: kwargs -> Redis -> settings
                cashier_name, cashier_inn = self._get_cashier(device_id, kwargs)
                self.fptr.setParam(1021, cashier_name)
                if cashier_inn:
                    self.fptr.setParam(1203, cashier_inn)
                self._check_result(self.fptr.operatorLogin(), "регистрации кассира")

                # Открытие смены
                self._check_result(self.fptr.openShift(), "открытия смены")
                self._check_result(self.fptr.checkDocumentClosed(), "проверки закрытия документа")

                shift_number = self.fptr.getParamInt(IFptr.LIBFPTR_PARAM_SHIFT_NUMBER)
                response['success'] = True
                response['message'] = f"Смена #{shift_number} успешно открыта"
                response['data'] = {'shift_number': shift_number}

            elif command == 'shift_close':
                # Получение кассира с приоритетом: kwargs -> Redis -> settings
                cashier_name, cashier_inn = self._get_cashier(device_id, kwargs)
                self.fptr.setParam(1021, cashier_name)
                if cashier_inn:
                    self.fptr.setParam(1203, cashier_inn)
                self._check_result(self.fptr.operatorLogin(), "регистрации кассира")

                # Закрытие смены через report()
                self.fptr.setParam(IFptr.LIBFPTR_PARAM_REPORT_TYPE, IFptr.LIBFPTR_RT_CLOSE_SHIFT)
                self._check_result(self.fptr.report(), "закрытия смены")
                self._check_result(self.fptr.checkDocumentClosed(), "проверки закрытия документа")

                response['success'] = True
                response['data'] = {
                    "shift_number": self.fptr.getParamInt(IFptr.LIBFPTR_PARAM_SHIFT_NUMBER),
                    "fiscal_document_number": self.fptr.getParamInt(IFptr.LIBFPTR_PARAM_FISCAL_DOCUMENT_NUMBER),
                }
                response['message'] = "Смена успешно закрыта, Z-отчет напечатан"

            elif command == 'shift_get_status':
                # Запрос состояния смены
                self.fptr.setParam(IFptr.LIBFPTR_PARAM_DATA_TYPE, IFptr.LIBFPTR_DT_SHIFT_STATE)
                self._check_result(self.fptr.queryData(), "запроса состояния смены")
                dt = self.fptr.getParamDateTime(IFptr.LIBFPTR_PARAM_DATE_TIME)
                shift_state = self.fptr.getParamInt(IFptr.LIBFPTR_PARAM_SHIFT_STATE)
                shift_number = self.fptr.getParamInt(IFptr.LIBFPTR_PARAM_SHIFT_NUMBER)

                # Расшифровка состояния смены
                shift_state_names = {
                    0: "Смена закрыта",
                    1: "Смена открыта",
                    2: "Смена истекла (больше 24 часов)"
                }

                response['success'] = True
                response['data'] = {
                    "shift_state": shift_state,
                    "shift_state_name": shift_state_names.get(shift_state, f"Неизвестное состояние ({shift_state})"),
                    "shift_number": shift_number,
                    "date_time": dt.isoformat() if isinstance(dt, datetime.datetime) else None,
                }
                response['message'] = "Статус смены получен"

            elif command == 'shift_print_x_report':
                # Получение кассира с приоритетом: kwargs -> Redis -> settings
                cashier_name, cashier_inn = self._get_cashier(device_id, kwargs)
                self.fptr.setParam(1021, cashier_name)
                if cashier_inn:
                    self.fptr.setParam(1203, cashier_inn)
                self._check_result(self.fptr.operatorLogin(), "регистрации кассира")

                # Печать X-отчета
                self.fptr.setParam(IFptr.LIBFPTR_PARAM_REPORT_TYPE, IFptr.LIBFPTR_RT_X)
                self._check_result(self.fptr.report(), "печати X-отчета")

                response['success'] = True
                response['message'] = "X-отчет успешно напечатан"

            # ======================================================================
            # Receipt Commands
            # ======================================================================
            elif command == 'receipt_open':
                # Получение кассира с приоритетом: kwargs -> Redis -> settings
                cashier_name, cashier_inn = self._get_cashier(device_id, kwargs)
                self.fptr.setParam(1021, cashier_name)
                if cashier_inn:
                    self.fptr.setParam(1203, cashier_inn)
                self._check_result(self.fptr.operatorLogin(), "регистрации кассира")

                # Открытие чека
                self.fptr.setParam(IFptr.LIBFPTR_PARAM_RECEIPT_TYPE, kwargs['receipt_type'])
                if kwargs.get('customer_contact'):
                    self.fptr.setParam(IFptr.LIBFPTR_PARAM_RECEIPT_ELECTRONICALLY, True)
                    self.fptr.setParam(IFptr.LIBFPTR_PARAM_BUYER_EMAIL_OR_PHONE, kwargs['customer_contact'])
                self._check_result(self.fptr.openReceipt(), "открытия чека")
                response['success'] = True
                response['message'] = f"Чек типа {kwargs['receipt_type']} успешно открыт"

            elif command == 'registration':
                for key, value in kwargs.items():
                    if key == 'name': self.fptr.setParam(IFptr.LIBFPTR_PARAM_COMMODITY_NAME, value)
                    elif key == 'price': self.fptr.setParam(IFptr.LIBFPTR_PARAM_PRICE, value)
                    elif key == 'quantity': self.fptr.setParam(IFptr.LIBFPTR_PARAM_QUANTITY, value)
                    elif key == 'tax_type': self.fptr.setParam(IFptr.LIBFPTR_PARAM_TAX_TYPE, value)
                    elif key == 'payment_method': self.fptr.setParam(IFptr.LIBFPTR_PARAM_PAYMENT_TYPE_SIGN, value)
                    elif key == 'payment_object': self.fptr.setParam(IFptr.LIBFPTR_PARAM_COMMODITY_SIGN, value)
                self._check_result(self.fptr.registration(), "регистрации позиции")
                response['success'] = True
                response['message'] = f"Позиция '{kwargs['name']}' добавлена"

            elif command == 'payment':
                self.fptr.setParam(IFptr.LIBFPTR_PARAM_PAYMENT_TYPE, kwargs['payment_type'])
                self.fptr.setParam(IFptr.LIBFPTR_PARAM_PAYMENT_SUM, kwargs['sum'])
                self._check_result(self.fptr.payment(), "регистрации оплаты")
                response['success'] = True
                response['message'] = f"Оплата {kwargs['sum']:.2f} добавлена"

            elif command == 'receipt_close':
                self._check_result(self.fptr.closeReceipt(), "закрытия чека")
                response['success'] = True
                response['data'] = None
                response['message'] = "Чек успешно закрыт и напечатан"

            elif command == 'receipt_cancel':
                self._check_result(self.fptr.cancelReceipt(), "отмены чека")
                response['success'] = True
                response['message'] = "Чек отменен"

            # ======================================================================
            # Sound Commands
            # ======================================================================
            elif command == 'beep':
                frequency = kwargs.get('frequency', 2000)
                duration = kwargs.get('duration', 100)
                self._play_beep(frequency, duration)
                response['success'] = True
                response['message'] = f"Звуковой сигнал воспроизведен (частота: {frequency} Гц, длительность: {duration} мс)"

            elif command == 'play_arcane_melody':
                self._play_arcane_melody()
                response['success'] = True
                response['message'] = "Мелодия 'Enemy' из Arcane успешно воспроизведена!"

            # ======================================================================
            # Cash Commands
            # ======================================================================
            elif command == 'cash_income':
                self.fptr.setParam(IFptr.LIBFPTR_PARAM_SUM, kwargs['amount'])
                self._check_result(self.fptr.cashIncome(), "внесения наличных")
                response['success'] = True
                response['message'] = f"Внесено наличных: {kwargs['amount']:.2f}"

            elif command == 'cash_outcome':
                self.fptr.setParam(IFptr.LIBFPTR_PARAM_SUM, kwargs['amount'])
                self._check_result(self.fptr.cashOutcome(), "выплаты наличных")
                response['success'] = True
                response['message'] = f"Выплачено наличных: {kwargs['amount']:.2f}"

            # ======================================================================
            # Print Commands
            # ======================================================================
            elif command == 'print_text':
                text = kwargs.get('text', '')
                # Обязательные параметры
                self.fptr.setParam(IFptr.LIBFPTR_PARAM_TEXT, text)
                self.fptr.setParam(IFptr.LIBFPTR_PARAM_ALIGNMENT, kwargs.get('alignment', IFptr.LIBFPTR_ALIGNMENT_LEFT))
                self.fptr.setParam(IFptr.LIBFPTR_PARAM_TEXT_WRAP, kwargs.get('wrap', IFptr.LIBFPTR_TW_NONE))

                # Опциональные параметры
                if 'font' in kwargs:
                    self.fptr.setParam(IFptr.LIBFPTR_PARAM_FONT, kwargs['font'])
                if 'double_width' in kwargs:
                    self.fptr.setParam(IFptr.LIBFPTR_PARAM_FONT_DOUBLE_WIDTH, kwargs['double_width'])
                if 'double_height' in kwargs:
                    self.fptr.setParam(IFptr.LIBFPTR_PARAM_FONT_DOUBLE_HEIGHT, kwargs['double_height'])
                if 'linespacing' in kwargs:
                    self.fptr.setParam(IFptr.LIBFPTR_PARAM_LINESPACING, kwargs['linespacing'])
                if 'brightness' in kwargs:
                    self.fptr.setParam(IFptr.LIBFPTR_PARAM_BRIGHTNESS, kwargs['brightness'])
                if 'defer' in kwargs and kwargs['defer'] != 0:
                    self.fptr.setParam(IFptr.LIBFPTR_PARAM_DEFER, kwargs['defer'])

                self._check_result(self.fptr.printText(), "печати текста")
                response['success'] = True
                response['message'] = f"Текст напечатан: '{text}'"

            elif command == 'print_feed':
                lines = kwargs.get('lines', 1)
                for _ in range(lines):
                    self._check_result(self.fptr.printText(), "промотки ленты")
                response['success'] = True
                response['message'] = f"Промотано строк: {lines}"

            elif command == 'print_barcode':
                barcode = kwargs['barcode']
                # Обязательные параметры
                self.fptr.setParam(IFptr.LIBFPTR_PARAM_BARCODE, barcode)
                self.fptr.setParam(IFptr.LIBFPTR_PARAM_BARCODE_TYPE, kwargs.get('barcode_type', IFptr.LIBFPTR_BT_QR))
                self.fptr.setParam(IFptr.LIBFPTR_PARAM_ALIGNMENT, kwargs.get('alignment', IFptr.LIBFPTR_ALIGNMENT_LEFT))
                self.fptr.setParam(IFptr.LIBFPTR_PARAM_SCALE, kwargs.get('scale', 2))

                # Опциональные параметры
                if 'left_margin' in kwargs:
                    self.fptr.setParam(IFptr.LIBFPTR_PARAM_LEFT_MARGIN, kwargs['left_margin'])
                if 'invert' in kwargs:
                    self.fptr.setParam(IFptr.LIBFPTR_PARAM_BARCODE_INVERT, kwargs['invert'])
                if 'height' in kwargs:
                    self.fptr.setParam(IFptr.LIBFPTR_PARAM_HEIGHT, kwargs['height'])
                if 'print_text' in kwargs:
                    self.fptr.setParam(IFptr.LIBFPTR_PARAM_BARCODE_PRINT_TEXT, kwargs['print_text'])
                if 'correction' in kwargs:
                    self.fptr.setParam(IFptr.LIBFPTR_PARAM_BARCODE_CORRECTION, kwargs['correction'])
                if 'version' in kwargs:
                    self.fptr.setParam(IFptr.LIBFPTR_PARAM_BARCODE_VERSION, kwargs['version'])
                if 'columns' in kwargs:
                    self.fptr.setParam(IFptr.LIBFPTR_PARAM_BARCODE_COLUMNS, kwargs['columns'])
                if 'defer' in kwargs and kwargs['defer'] != 0:
                    self.fptr.setParam(IFptr.LIBFPTR_PARAM_DEFER, kwargs['defer'])

                self._check_result(self.fptr.printBarcode(), "печати штрихкода")
                response['success'] = True
                response['message'] = f"Штрихкод напечатан: '{barcode}'"

            elif command == 'print_picture':
                filename = kwargs['filename']
                # Обязательные параметры
                self.fptr.setParam(IFptr.LIBFPTR_PARAM_FILENAME, filename)
                self.fptr.setParam(IFptr.LIBFPTR_PARAM_ALIGNMENT, kwargs.get('alignment', IFptr.LIBFPTR_ALIGNMENT_LEFT))
                self.fptr.setParam(IFptr.LIBFPTR_PARAM_SCALE_PERCENT, kwargs.get('scale_percent', 100))

                # Опциональные параметры
                if 'left_margin' in kwargs:
                    self.fptr.setParam(IFptr.LIBFPTR_PARAM_LEFT_MARGIN, kwargs['left_margin'])

                self._check_result(self.fptr.printPicture(), "печати картинки")
                response['success'] = True
                response['message'] = f"Картинка напечатана: '{filename}'"

            elif command == 'print_picture_by_number':
                picture_number = kwargs['picture_number']
                # Обязательные параметры
                self.fptr.setParam(IFptr.LIBFPTR_PARAM_PICTURE_NUMBER, picture_number)
                self.fptr.setParam(IFptr.LIBFPTR_PARAM_ALIGNMENT, kwargs.get('alignment', IFptr.LIBFPTR_ALIGNMENT_LEFT))

                # Опциональные параметры
                if 'left_margin' in kwargs:
                    self.fptr.setParam(IFptr.LIBFPTR_PARAM_LEFT_MARGIN, kwargs['left_margin'])
                if 'defer' in kwargs and kwargs['defer'] != 0:
                    self.fptr.setParam(IFptr.LIBFPTR_PARAM_DEFER, kwargs['defer'])

                self._check_result(self.fptr.printPictureByNumber(), "печати картинки из памяти")
                response['success'] = True
                response['message'] = f"Картинка №{picture_number} напечатана"

            elif command == 'open_nonfiscal_document':
                self._check_result(self.fptr.beginNonfiscalDocument(), "открытия нефискального документа")
                response['success'] = True
                response['message'] = "Нефискальный документ открыт"

            elif command == 'close_nonfiscal_document':
                self._check_result(self.fptr.endNonfiscalDocument(), "закрытия нефискального документа")
                response['success'] = True
                response['message'] = "Нефискальный документ закрыт"

            elif command == 'cut_paper':
                self._check_result(self.fptr.cut(), "отрезания чека")
                response['success'] = True
                response['message'] = "Чек отрезан"

            elif command == 'open_cash_drawer':
                self._check_result(self.fptr.openCashDrawer(), "открытия денежного ящика")
                response['success'] = True
                response['message'] = "Денежный ящик открыт"

            elif command == 'print_x_report':
                self.fptr.setParam(IFptr.LIBFPTR_PARAM_REPORT_TYPE, IFptr.LIBFPTR_RT_X)
                self._check_result(self.fptr.report(), "печати X-отчета")
                response['success'] = True
                response['message'] = "X-отчет напечатан"

            # ======================================================================
            # Query Commands (All of them)
            # ======================================================================
            elif command == 'get_status':
                self.fptr.setParam(IFptr.LIBFPTR_PARAM_DATA_TYPE, IFptr.LIBFPTR_DT_STATUS)
                self._check_result(self.fptr.queryData(), "запроса статуса")
                response['data'] = {
                    "model_name": self.fptr.getParamString(IFptr.LIBFPTR_PARAM_MODEL_NAME),
                    "serial_number": self.fptr.getParamString(IFptr.LIBFPTR_PARAM_SERIAL_NUMBER),
                    "shift_state": self.fptr.getParamInt(IFptr.LIBFPTR_PARAM_SHIFT_STATE),
                    "cover_opened": self.fptr.getParamBool(IFptr.LIBFPTR_PARAM_COVER_OPENED),
                    "paper_present": self.fptr.getParamBool(IFptr.LIBFPTR_PARAM_RECEIPT_PAPER_PRESENT),
                }
                response['success'] = True

            elif command == 'get_short_status':
                self.fptr.setParam(IFptr.LIBFPTR_PARAM_DATA_TYPE, IFptr.LIBFPTR_DT_SHORT_STATUS)
                self._check_result(self.fptr.queryData(), "короткого запроса статуса")
                response['data'] = {
                    "cashdrawer_opened": self.fptr.getParamBool(IFptr.LIBFPTR_PARAM_CASHDRAWER_OPENED),
                    "paper_present": self.fptr.getParamBool(IFptr.LIBFPTR_PARAM_RECEIPT_PAPER_PRESENT),
                    "paper_near_end": self.fptr.getParamBool(IFptr.LIBFPTR_PARAM_PAPER_NEAR_END),
                    "cover_opened": self.fptr.getParamBool(IFptr.LIBFPTR_PARAM_COVER_OPENED),
                }
                response['success'] = True

            elif command == 'get_cash_sum':
                self.fptr.setParam(IFptr.LIBFPTR_PARAM_DATA_TYPE, IFptr.LIBFPTR_DT_CASH_SUM)
                self._check_result(self.fptr.queryData(), "запроса суммы наличных")
                response['data'] = {"cash_sum": self.fptr.getParamDouble(IFptr.LIBFPTR_PARAM_SUM)}
                response['success'] = True

            elif command == 'get_shift_state':
                self.fptr.setParam(IFptr.LIBFPTR_PARAM_DATA_TYPE, IFptr.LIBFPTR_DT_SHIFT_STATE)
                self._check_result(self.fptr.queryData(), "запроса состояния смены")
                dt = self.fptr.getParamDateTime(IFptr.LIBFPTR_PARAM_DATE_TIME)
                response['data'] = {
                    "shift_state": self.fptr.getParamInt(IFptr.LIBFPTR_PARAM_SHIFT_STATE),
                    "shift_number": self.fptr.getParamInt(IFptr.LIBFPTR_PARAM_SHIFT_NUMBER),
                    "date_time": dt.isoformat() if isinstance(dt, datetime.datetime) else None,
                }
                response['success'] = True

            elif command == 'get_receipt_state':
                self.fptr.setParam(IFptr.LIBFPTR_PARAM_DATA_TYPE, IFptr.LIBFPTR_DT_RECEIPT_STATE)
                self._check_result(self.fptr.queryData(), "запроса состояния чека")
                response['data'] = {
                    "receipt_type": self.fptr.getParamInt(IFptr.LIBFPTR_PARAM_RECEIPT_TYPE),
                    "receipt_sum": self.fptr.getParamDouble(IFptr.LIBFPTR_PARAM_RECEIPT_SUM),
                    "receipt_number": self.fptr.getParamInt(IFptr.LIBFPTR_PARAM_RECEIPT_NUMBER),
                    "document_number": self.fptr.getParamInt(IFptr.LIBFPTR_PARAM_DOCUMENT_NUMBER),
                    "remainder": self.fptr.getParamDouble(IFptr.LIBFPTR_PARAM_REMAINDER),
                    "change": self.fptr.getParamDouble(IFptr.LIBFPTR_PARAM_CHANGE),
                }
                response['success'] = True

            elif command == 'get_datetime':
                self.fptr.setParam(IFptr.LIBFPTR_PARAM_DATA_TYPE, IFptr.LIBFPTR_DT_DATE_TIME)
                self._check_result(self.fptr.queryData(), "запроса даты и времени")
                dt = self.fptr.getParamDateTime(IFptr.LIBFPTR_PARAM_DATE_TIME)
                response['data'] = {
                    "date_time": dt.isoformat() if isinstance(dt, datetime.datetime) else None
                }
                response['success'] = True

            elif command == 'get_serial_number':
                self.fptr.setParam(IFptr.LIBFPTR_PARAM_DATA_TYPE, IFptr.LIBFPTR_DT_SERIAL_NUMBER)
                self._check_result(self.fptr.queryData(), "запроса заводского номера")
                response['data'] = {
                    "serial_number": self.fptr.getParamString(IFptr.LIBFPTR_PARAM_SERIAL_NUMBER)
                }
                response['success'] = True

            elif command == 'get_model_info':
                self.fptr.setParam(IFptr.LIBFPTR_PARAM_DATA_TYPE, IFptr.LIBFPTR_DT_MODEL_INFO)
                self._check_result(self.fptr.queryData(), "запроса информации о модели")
                response['data'] = {
                    "model": self.fptr.getParamInt(IFptr.LIBFPTR_PARAM_MODEL),
                    "model_name": self.fptr.getParamString(IFptr.LIBFPTR_PARAM_MODEL_NAME),
                    "firmware_version": self.fptr.getParamString(IFptr.LIBFPTR_PARAM_UNIT_VERSION),
                }
                response['success'] = True

            elif command == 'get_receipt_line_length':
                self.fptr.setParam(IFptr.LIBFPTR_PARAM_DATA_TYPE, IFptr.LIBFPTR_DT_RECEIPT_LINE_LENGTH)
                self._check_result(self.fptr.queryData(), "запроса ширины чековой ленты")
                response['data'] = {
                    "char_line_length": self.fptr.getParamInt(IFptr.LIBFPTR_PARAM_RECEIPT_LINE_LENGTH),
                    "pix_line_length": self.fptr.getParamInt(IFptr.LIBFPTR_PARAM_RECEIPT_LINE_LENGTH_PIX),
                }
                response['success'] = True

            elif command == 'get_unit_version':
                unit_type = kwargs.get('unit_type', IFptr.LIBFPTR_UT_FIRMWARE)
                self.fptr.setParam(IFptr.LIBFPTR_PARAM_DATA_TYPE, IFptr.LIBFPTR_DT_UNIT_VERSION)
                self.fptr.setParam(IFptr.LIBFPTR_PARAM_UNIT_TYPE, unit_type)
                self._check_result(self.fptr.queryData(), "запроса версии модуля")
                result_data = {
                    "unit_version": self.fptr.getParamString(IFptr.LIBFPTR_PARAM_UNIT_VERSION)
                }
                # Для конфигурации также возвращается версия релиза
                if unit_type == IFptr.LIBFPTR_UT_CONFIGURATION:
                    result_data["release_version"] = self.fptr.getParamString(IFptr.LIBFPTR_PARAM_UNIT_RELEASE_VERSION)
                response['data'] = result_data
                response['success'] = True

            elif command == 'get_payment_sum':
                payment_type = kwargs['payment_type']
                receipt_type = kwargs['receipt_type']
                self.fptr.setParam(IFptr.LIBFPTR_PARAM_DATA_TYPE, IFptr.LIBFPTR_DT_PAYMENT_SUM)
                self.fptr.setParam(IFptr.LIBFPTR_PARAM_PAYMENT_TYPE, payment_type)
                self.fptr.setParam(IFptr.LIBFPTR_PARAM_RECEIPT_TYPE, receipt_type)
                self._check_result(self.fptr.queryData(), "запроса суммы платежей")
                response['data'] = {
                    "sum": self.fptr.getParamDouble(IFptr.LIBFPTR_PARAM_SUM)
                }
                response['success'] = True

            elif command == 'get_cashin_sum':
                self.fptr.setParam(IFptr.LIBFPTR_PARAM_DATA_TYPE, IFptr.LIBFPTR_DT_CASHIN_SUM)
                self._check_result(self.fptr.queryData(), "запроса суммы внесений")
                response['data'] = {"sum": self.fptr.getParamDouble(IFptr.LIBFPTR_PARAM_SUM)}
                response['success'] = True

            elif command == 'get_cashout_sum':
                self.fptr.setParam(IFptr.LIBFPTR_PARAM_DATA_TYPE, IFptr.LIBFPTR_DT_CASHOUT_SUM)
                self._check_result(self.fptr.queryData(), "запроса суммы выплат")
                response['data'] = {"sum": self.fptr.getParamDouble(IFptr.LIBFPTR_PARAM_SUM)}
                response['success'] = True

            elif command == 'get_receipt_count':
                receipt_type = kwargs['receipt_type']
                self.fptr.setParam(IFptr.LIBFPTR_PARAM_DATA_TYPE, IFptr.LIBFPTR_DT_RECEIPT_COUNT)
                self.fptr.setParam(IFptr.LIBFPTR_PARAM_RECEIPT_TYPE, receipt_type)
                self._check_result(self.fptr.queryData(), "запроса количества чеков")
                response['data'] = {
                    "count": self.fptr.getParamInt(IFptr.LIBFPTR_PARAM_DOCUMENTS_COUNT)
                }
                response['success'] = True

            elif command == 'get_non_nullable_sum':
                receipt_type = kwargs['receipt_type']
                self.fptr.setParam(IFptr.LIBFPTR_PARAM_DATA_TYPE, IFptr.LIBFPTR_DT_NON_NULLABLE_SUM)
                self.fptr.setParam(IFptr.LIBFPTR_PARAM_RECEIPT_TYPE, receipt_type)
                self._check_result(self.fptr.queryData(), "запроса необнуляемой суммы")
                response['data'] = {
                    "sum": self.fptr.getParamDouble(IFptr.LIBFPTR_PARAM_SUM)
                }
                response['success'] = True

            elif command == 'get_power_source_state':
                power_source_type = kwargs.get('power_source_type', IFptr.LIBFPTR_PST_BATTERY)
                self.fptr.setParam(IFptr.LIBFPTR_PARAM_DATA_TYPE, IFptr.LIBFPTR_DT_POWER_SOURCE_STATE)
                self.fptr.setParam(IFptr.LIBFPTR_PARAM_POWER_SOURCE_TYPE, power_source_type)
                self._check_result(self.fptr.queryData(), "запроса состояния источника питания")
                response['data'] = {
                    "battery_charge": self.fptr.getParamInt(IFptr.LIBFPTR_PARAM_BATTERY_CHARGE),
                    "voltage": self.fptr.getParamDouble(IFptr.LIBFPTR_PARAM_VOLTAGE),
                    "use_battery": self.fptr.getParamBool(IFptr.LIBFPTR_PARAM_USE_BATTERY),
                    "battery_charging": self.fptr.getParamBool(IFptr.LIBFPTR_PARAM_BATTERY_CHARGING),
                    "can_print_while_on_battery": self.fptr.getParamBool(IFptr.LIBFPTR_PARAM_CAN_PRINT_WHILE_ON_BATTERY),
                }
                response['success'] = True

            elif command == 'get_printer_temperature':
                self.fptr.setParam(IFptr.LIBFPTR_PARAM_DATA_TYPE, IFptr.LIBFPTR_DT_PRINTER_TEMPERATURE)
                self._check_result(self.fptr.queryData(), "запроса температуры ТПГ")
                response['data'] = {
                    "printer_temperature": self.fptr.getParamDouble(IFptr.LIBFPTR_PARAM_PRINTER_TEMPERATURE)
                }
                response['success'] = True

            elif command == 'get_fatal_status':
                self.fptr.setParam(IFptr.LIBFPTR_PARAM_DATA_TYPE, IFptr.LIBFPTR_DT_FATAL_STATUS)
                self._check_result(self.fptr.queryData(), "запроса фатальных ошибок")
                response['data'] = {
                    "no_serial_number": self.fptr.getParamBool(IFptr.LIBFPTR_PARAM_NO_SERIAL_NUMBER),
                    "rtc_fault": self.fptr.getParamBool(IFptr.LIBFPTR_PARAM_RTC_FAULT),
                    "settings_fault": self.fptr.getParamBool(IFptr.LIBFPTR_PARAM_SETTINGS_FAULT),
                    "counters_fault": self.fptr.getParamBool(IFptr.LIBFPTR_PARAM_COUNTERS_FAULT),
                    "user_memory_fault": self.fptr.getParamBool(IFptr.LIBFPTR_PARAM_USER_MEMORY_FAULT),
                    "service_counters_fault": self.fptr.getParamBool(IFptr.LIBFPTR_PARAM_SERVICE_COUNTERS_FAULT),
                    "attributes_fault": self.fptr.getParamBool(IFptr.LIBFPTR_PARAM_ATTRIBUTES_FAULT),
                    "fn_fault": self.fptr.getParamBool(IFptr.LIBFPTR_PARAM_FN_FAULT),
                    "invalid_fn": self.fptr.getParamBool(IFptr.LIBFPTR_PARAM_INVALID_FN),
                    "hard_fault": self.fptr.getParamBool(IFptr.LIBFPTR_PARAM_HARD_FAULT),
                    "memory_manager_fault": self.fptr.getParamBool(IFptr.LIBFPTR_PARAM_MEMORY_MANAGER_FAULT),
                    "scripts_fault": self.fptr.getParamBool(IFptr.LIBFPTR_PARAM_SCRIPTS_FAULT),
                    "wait_for_reboot": self.fptr.getParamBool(IFptr.LIBFPTR_PARAM_WAIT_FOR_REBOOT),
                    "universal_counters_fault": self.fptr.getParamBool(IFptr.LIBFPTR_PARAM_UNIVERSAL_COUNTERS_FAULT),
                    "commodities_table_fault": self.fptr.getParamBool(IFptr.LIBFPTR_PARAM_COMMODITIES_TABLE_FAULT),
                }
                response['success'] = True

            elif command == 'get_mac_address':
                self.fptr.setParam(IFptr.LIBFPTR_PARAM_DATA_TYPE, IFptr.LIBFPTR_DT_MAC_ADDRESS)
                self._check_result(self.fptr.queryData(), "запроса MAC-адреса")
                response['data'] = {
                    "mac_address": self.fptr.getParamString(IFptr.LIBFPTR_PARAM_MAC_ADDRESS)
                }
                response['success'] = True

            elif command == 'get_ethernet_info':
                self.fptr.setParam(IFptr.LIBFPTR_PARAM_DATA_TYPE, IFptr.LIBFPTR_DT_ETHERNET_INFO)
                self._check_result(self.fptr.queryData(), "запроса конфигурации Ethernet")
                response['data'] = {
                    "ip": self.fptr.getParamString(IFptr.LIBFPTR_PARAM_ETHERNET_IP),
                    "mask": self.fptr.getParamString(IFptr.LIBFPTR_PARAM_ETHERNET_MASK),
                    "gateway": self.fptr.getParamString(IFptr.LIBFPTR_PARAM_ETHERNET_GATEWAY),
                    "dns": self.fptr.getParamString(IFptr.LIBFPTR_PARAM_ETHERNET_DNS_IP),
                    "timeout": self.fptr.getParamInt(IFptr.LIBFPTR_PARAM_ETHERNET_CONFIG_TIMEOUT),
                    "port": self.fptr.getParamInt(IFptr.LIBFPTR_PARAM_ETHERNET_PORT),
                    "dhcp": self.fptr.getParamBool(IFptr.LIBFPTR_PARAM_ETHERNET_DHCP),
                    "dns_static": self.fptr.getParamBool(IFptr.LIBFPTR_PARAM_ETHERNET_DNS_STATIC),
                }
                response['success'] = True

            elif command == 'get_wifi_info':
                self.fptr.setParam(IFptr.LIBFPTR_PARAM_DATA_TYPE, IFptr.LIBFPTR_DT_WIFI_INFO)
                self._check_result(self.fptr.queryData(), "запроса конфигурации Wi-Fi")
                response['data'] = {
                    "ip": self.fptr.getParamString(IFptr.LIBFPTR_PARAM_WIFI_IP),
                    "mask": self.fptr.getParamString(IFptr.LIBFPTR_PARAM_WIFI_MASK),
                    "gateway": self.fptr.getParamString(IFptr.LIBFPTR_PARAM_WIFI_GATEWAY),
                    "timeout": self.fptr.getParamInt(IFptr.LIBFPTR_PARAM_WIFI_CONFIG_TIMEOUT),
                    "port": self.fptr.getParamInt(IFptr.LIBFPTR_PARAM_WIFI_PORT),
                    "dhcp": self.fptr.getParamBool(IFptr.LIBFPTR_PARAM_WIFI_DHCP),
                }
                response['success'] = True

            # ======================================================================
            # Operator & Document Commands
            # ======================================================================
            elif command == 'operator_login':
                operator_name = kwargs['operator_name']
                operator_vatin = kwargs.get('operator_vatin', '')
                self.fptr.setParam(1021, operator_name)
                if operator_vatin:
                    self.fptr.setParam(1203, operator_vatin)
                self._check_result(self.fptr.operatorLogin(), "регистрации кассира")
                response['success'] = True
                response['message'] = f"Кассир '{operator_name}' зарегистрирован"

            elif command == 'continue_print':
                self._check_result(self.fptr.continuePrint(), "допечатывания документа")
                response['success'] = True
                response['message'] = "Документ допечатан"

            elif command == 'check_document_closed':
                self._check_result(self.fptr.checkDocumentClosed(), "проверки закрытия документа")
                response['data'] = {
                    "document_closed": self.fptr.getParamBool(IFptr.LIBFPTR_PARAM_DOCUMENT_CLOSED),
                    "document_printed": self.fptr.getParamBool(IFptr.LIBFPTR_PARAM_DOCUMENT_PRINTED),
                }
                response['success'] = True
                response['message'] = "Состояние документа проверено"

            # ======================================================================
            # Configuration Commands
            # ======================================================================
            elif command == 'configure_logging':
                # Создаем конфигурацию логирования
                from .config.logging_config import LoggingConfig

                config = LoggingConfig()

                # Устанавливаем уровни для категорий
                if 'root_level' in kwargs:
                    config.set_root_level(kwargs['root_level'])
                if 'fiscal_printer_level' in kwargs:
                    config.set_category_level('FiscalPrinter', kwargs['fiscal_printer_level'])
                if 'transport_level' in kwargs:
                    config.set_category_level('Transport', kwargs['transport_level'])
                if 'ethernet_over_transport_level' in kwargs:
                    config.set_category_level('EthernetOverTransport', kwargs['ethernet_over_transport_level'])
                if 'device_debug_level' in kwargs:
                    config.set_category_level('DeviceDebug', kwargs['device_debug_level'])
                if 'usb_level' in kwargs:
                    config.set_category_level('USB', kwargs['usb_level'])
                if 'com_level' in kwargs:
                    config.set_category_level('COM', kwargs['com_level'])
                if 'tcp_level' in kwargs:
                    config.set_category_level('TCP', kwargs['tcp_level'])
                if 'bluetooth_level' in kwargs:
                    config.set_category_level('Bluetooth', kwargs['bluetooth_level'])

                # Включить консольный вывод
                if kwargs.get('enable_console', False):
                    config.enable_console_logging()

                # Установить количество дней хранения
                if 'max_days_keep' in kwargs:
                    config.set_max_days_keep(kwargs['max_days_keep'])

                # Применить конфигурацию
                config.write_config()

                response['success'] = True
                response['message'] = "Конфигурация логирования обновлена"
                response['data'] = {'config_path': config.get_config_path()}

            elif command == 'change_driver_label':
                label = kwargs['label']
                self.driver.change_label(label)
                response['success'] = True
                response['message'] = f"Метка драйвера изменена на: {label}"

            elif command == 'get_default_logging_config':
                from .config.logging_config import LoggingConfig

                config = LoggingConfig()
                default_config = config.get_default_config()

                response['success'] = True
                response['message'] = "Конфигурация по умолчанию получена"
                response['data'] = default_config

            # ======================================================================
            # Read Records Commands (Чтение данных из ФН и ККТ)
            # ======================================================================
            elif command == 'read_fn_document':
                document_number = kwargs['document_number']

                # Начинаем чтение документа из ФН
                self.fptr.setParam(IFptr.LIBFPTR_PARAM_RECORDS_TYPE, IFptr.LIBFPTR_RT_FN_DOCUMENT_TLVS)
                self.fptr.setParam(IFptr.LIBFPTR_PARAM_DOCUMENT_NUMBER, document_number)
                self._check_result(self.fptr.beginReadRecords(), "начала чтения документа из ФН")

                # Получаем информацию о документе
                document_type = self.fptr.getParamInt(IFptr.LIBFPTR_PARAM_FN_DOCUMENT_TYPE)
                document_size = self.fptr.getParamInt(IFptr.LIBFPTR_PARAM_COUNT)
                records_id = self.fptr.getParamString(IFptr.LIBFPTR_PARAM_RECORDS_ID)

                # Читаем все TLV-записи
                tlv_records = []
                self.fptr.setParam(IFptr.LIBFPTR_PARAM_RECORDS_ID, records_id)
                while self.fptr.readNextRecord() == 0:  # 0 = LIBFPTR_OK
                    tag_number = self.fptr.getParamInt(IFptr.LIBFPTR_PARAM_TAG_NUMBER)
                    tag_name = self.fptr.getParamString(IFptr.LIBFPTR_PARAM_TAG_NAME)
                    tag_type = self.fptr.getParamInt(IFptr.LIBFPTR_PARAM_TAG_TYPE)
                    is_complex = self.fptr.getParamBool(IFptr.LIBFPTR_PARAM_TAG_IS_COMPLEX)
                    is_repeatable = self.fptr.getParamBool(IFptr.LIBFPTR_PARAM_TAG_IS_REPEATABLE)

                    # Читаем значение в зависимости от типа
                    tag_value = None
                    try:
                        if tag_type in [4, 5, 6, 7]:  # BYTE, UINT_16, UINT_32, VLN
                            tag_value = self.fptr.getParamInt(IFptr.LIBFPTR_PARAM_TAG_VALUE)
                        elif tag_type == 3:  # FVLN (float)
                            tag_value = self.fptr.getParamDouble(IFptr.LIBFPTR_PARAM_TAG_VALUE)
                        elif tag_type == 8:  # STRING
                            tag_value = self.fptr.getParamString(IFptr.LIBFPTR_PARAM_TAG_VALUE)
                        elif tag_type == 10:  # BOOL
                            tag_value = self.fptr.getParamBool(IFptr.LIBFPTR_PARAM_TAG_VALUE)
                        else:  # STLV, ARRAY, BITS, UNIX_TIME
                            tag_value = list(self.fptr.getParamByteArray(IFptr.LIBFPTR_PARAM_TAG_VALUE))
                    except:
                        tag_value = list(self.fptr.getParamByteArray(IFptr.LIBFPTR_PARAM_TAG_VALUE))

                    tlv_records.append({
                        "tag_number": tag_number,
                        "tag_name": tag_name,
                        "tag_type": tag_type,
                        "tag_value": tag_value,
                        "is_complex": is_complex,
                        "is_repeatable": is_repeatable
                    })

                    self.fptr.setParam(IFptr.LIBFPTR_PARAM_RECORDS_ID, records_id)

                # Завершаем чтение
                self.fptr.setParam(IFptr.LIBFPTR_PARAM_RECORDS_ID, records_id)
                self._check_result(self.fptr.endReadRecords(), "завершения чтения документа")

                response['success'] = True
                response['message'] = f"Документ №{document_number} успешно прочитан из ФН"
                response['data'] = {
                    "document_number": document_number,
                    "document_type": document_type,
                    "document_size": document_size,
                    "tlv_records": tlv_records
                }

            elif command == 'read_licenses':
                # Начинаем чтение лицензий
                self.fptr.setParam(IFptr.LIBFPTR_PARAM_RECORDS_TYPE, IFptr.LIBFPTR_RT_LICENSES)
                self._check_result(self.fptr.beginReadRecords(), "начала чтения лицензий")

                records_id = self.fptr.getParamString(IFptr.LIBFPTR_PARAM_RECORDS_ID)

                # Читаем все лицензии
                licenses = []
                self.fptr.setParam(IFptr.LIBFPTR_PARAM_RECORDS_ID, records_id)
                while self.fptr.readNextRecord() == 0:  # 0 = LIBFPTR_OK
                    license_number = self.fptr.getParamInt(IFptr.LIBFPTR_PARAM_LICENSE_NUMBER)
                    license_name = self.fptr.getParamString(IFptr.LIBFPTR_PARAM_LICENSE_NAME)
                    date_from = self.fptr.getParamDateTime(IFptr.LIBFPTR_PARAM_LICENSE_VALID_FROM)
                    date_until = self.fptr.getParamDateTime(IFptr.LIBFPTR_PARAM_LICENSE_VALID_UNTIL)

                    licenses.append({
                        "license_number": license_number,
                        "license_name": license_name,
                        "valid_from": date_from.isoformat() if isinstance(date_from, datetime.datetime) else "1970-01-01T00:00:00",
                        "valid_until": date_until.isoformat() if isinstance(date_until, datetime.datetime) else "1970-01-01T00:00:00"
                    })

                    self.fptr.setParam(IFptr.LIBFPTR_PARAM_RECORDS_ID, records_id)

                # Завершаем чтение
                self.fptr.setParam(IFptr.LIBFPTR_PARAM_RECORDS_ID, records_id)
                self._check_result(self.fptr.endReadRecords(), "завершения чтения лицензий")

                response['success'] = True
                response['message'] = f"Прочитано лицензий: {len(licenses)}"
                response['data'] = {"licenses": licenses}

            elif command == 'read_registration_document':
                registration_number = kwargs['registration_number']

                # Начинаем чтение документа регистрации
                self.fptr.setParam(IFptr.LIBFPTR_PARAM_RECORDS_TYPE, IFptr.LIBFPTR_RT_FN_REGISTRATION_TLVS)
                self.fptr.setParam(IFptr.LIBFPTR_PARAM_REGISTRATION_NUMBER, registration_number)
                self._check_result(self.fptr.beginReadRecords(), "начала чтения документа регистрации")

                records_id = self.fptr.getParamString(IFptr.LIBFPTR_PARAM_RECORDS_ID)

                # Читаем все TLV-записи
                tlv_records = []
                self.fptr.setParam(IFptr.LIBFPTR_PARAM_RECORDS_ID, records_id)
                while self.fptr.readNextRecord() == 0:  # 0 = LIBFPTR_OK
                    tag_number = self.fptr.getParamInt(IFptr.LIBFPTR_PARAM_TAG_NUMBER)
                    tag_name = self.fptr.getParamString(IFptr.LIBFPTR_PARAM_TAG_NAME)
                    tag_type = self.fptr.getParamInt(IFptr.LIBFPTR_PARAM_TAG_TYPE)
                    is_complex = self.fptr.getParamBool(IFptr.LIBFPTR_PARAM_TAG_IS_COMPLEX)
                    is_repeatable = self.fptr.getParamBool(IFptr.LIBFPTR_PARAM_TAG_IS_REPEATABLE)

                    # Читаем значение в зависимости от типа
                    tag_value = None
                    try:
                        if tag_type in [4, 5, 6, 7]:  # BYTE, UINT_16, UINT_32, VLN
                            tag_value = self.fptr.getParamInt(IFptr.LIBFPTR_PARAM_TAG_VALUE)
                        elif tag_type == 3:  # FVLN (float)
                            tag_value = self.fptr.getParamDouble(IFptr.LIBFPTR_PARAM_TAG_VALUE)
                        elif tag_type == 8:  # STRING
                            tag_value = self.fptr.getParamString(IFptr.LIBFPTR_PARAM_TAG_VALUE)
                        elif tag_type == 10:  # BOOL
                            tag_value = self.fptr.getParamBool(IFptr.LIBFPTR_PARAM_TAG_VALUE)
                        else:  # STLV, ARRAY, BITS, UNIX_TIME
                            tag_value = list(self.fptr.getParamByteArray(IFptr.LIBFPTR_PARAM_TAG_VALUE))
                    except:
                        tag_value = list(self.fptr.getParamByteArray(IFptr.LIBFPTR_PARAM_TAG_VALUE))

                    tlv_records.append({
                        "tag_number": tag_number,
                        "tag_name": tag_name,
                        "tag_type": tag_type,
                        "tag_value": tag_value,
                        "is_complex": is_complex,
                        "is_repeatable": is_repeatable
                    })

                    self.fptr.setParam(IFptr.LIBFPTR_PARAM_RECORDS_ID, records_id)

                # Завершаем чтение
                self.fptr.setParam(IFptr.LIBFPTR_PARAM_RECORDS_ID, records_id)
                self._check_result(self.fptr.endReadRecords(), "завершения чтения документа регистрации")

                response['success'] = True
                response['message'] = f"Документ регистрации №{registration_number} успешно прочитан"
                response['data'] = {
                    "registration_number": registration_number,
                    "tlv_records": tlv_records
                }

            elif command == 'parse_complex_attribute':
                tag_value_bytes = bytes(kwargs['tag_value'])

                # Начинаем разбор составного реквизита
                self.fptr.setParam(IFptr.LIBFPTR_PARAM_RECORDS_TYPE, IFptr.LIBFPTR_RT_PARSE_COMPLEX_ATTR)
                self.fptr.setParam(IFptr.LIBFPTR_PARAM_TAG_VALUE, tag_value_bytes)
                self._check_result(self.fptr.beginReadRecords(), "начала разбора составного реквизита")

                records_id = self.fptr.getParamString(IFptr.LIBFPTR_PARAM_RECORDS_ID)

                # Читаем все вложенные реквизиты
                parsed_records = []
                self.fptr.setParam(IFptr.LIBFPTR_PARAM_RECORDS_ID, records_id)
                while self.fptr.readNextRecord() == 0:  # 0 = LIBFPTR_OK
                    tag_number = self.fptr.getParamInt(IFptr.LIBFPTR_PARAM_TAG_NUMBER)
                    tag_name = self.fptr.getParamString(IFptr.LIBFPTR_PARAM_TAG_NAME)
                    tag_type = self.fptr.getParamInt(IFptr.LIBFPTR_PARAM_TAG_TYPE)
                    is_complex = self.fptr.getParamBool(IFptr.LIBFPTR_PARAM_TAG_IS_COMPLEX)
                    is_repeatable = self.fptr.getParamBool(IFptr.LIBFPTR_PARAM_TAG_IS_REPEATABLE)

                    # Читаем значение в зависимости от типа
                    tag_value = None
                    try:
                        if tag_type in [4, 5, 6, 7]:  # BYTE, UINT_16, UINT_32, VLN
                            tag_value = self.fptr.getParamInt(IFptr.LIBFPTR_PARAM_TAG_VALUE)
                        elif tag_type == 3:  # FVLN (float)
                            tag_value = self.fptr.getParamDouble(IFptr.LIBFPTR_PARAM_TAG_VALUE)
                        elif tag_type == 8:  # STRING
                            tag_value = self.fptr.getParamString(IFptr.LIBFPTR_PARAM_TAG_VALUE)
                        elif tag_type == 10:  # BOOL
                            tag_value = self.fptr.getParamBool(IFptr.LIBFPTR_PARAM_TAG_VALUE)
                        else:  # STLV, ARRAY, BITS, UNIX_TIME
                            tag_value = list(self.fptr.getParamByteArray(IFptr.LIBFPTR_PARAM_TAG_VALUE))
                    except:
                        tag_value = list(self.fptr.getParamByteArray(IFptr.LIBFPTR_PARAM_TAG_VALUE))

                    parsed_records.append({
                        "tag_number": tag_number,
                        "tag_name": tag_name,
                        "tag_type": tag_type,
                        "tag_value": tag_value,
                        "is_complex": is_complex,
                        "is_repeatable": is_repeatable
                    })

                    self.fptr.setParam(IFptr.LIBFPTR_PARAM_RECORDS_ID, records_id)

                # Завершаем разбор
                self.fptr.setParam(IFptr.LIBFPTR_PARAM_RECORDS_ID, records_id)
                self._check_result(self.fptr.endReadRecords(), "завершения разбора составного реквизита")

                response['success'] = True
                response['message'] = f"Составной реквизит успешно разобран, найдено элементов: {len(parsed_records)}"
                response['data'] = {"parsed_records": parsed_records}

            elif command == 'read_kkt_settings':
                # Начинаем чтение настроек
                self.fptr.setParam(IFptr.LIBFPTR_PARAM_RECORDS_TYPE, IFptr.LIBFPTR_RT_SETTINGS)
                self._check_result(self.fptr.beginReadRecords(), "начала чтения настроек ККТ")

                records_id = self.fptr.getParamString(IFptr.LIBFPTR_PARAM_RECORDS_ID)

                # Читаем все настройки
                settings = []
                self.fptr.setParam(IFptr.LIBFPTR_PARAM_RECORDS_ID, records_id)
                while self.fptr.readNextRecord() == 0:  # 0 = LIBFPTR_OK
                    setting_id = self.fptr.getParamInt(IFptr.LIBFPTR_PARAM_SETTING_ID)
                    setting_type = self.fptr.getParamInt(IFptr.LIBFPTR_PARAM_SETTING_TYPE)
                    setting_name = self.fptr.getParamString(IFptr.LIBFPTR_PARAM_SETTING_NAME)

                    # Читаем значение в зависимости от типа
                    if setting_type == IFptr.LIBFPTR_ST_NUMBER:
                        setting_value = self.fptr.getParamInt(IFptr.LIBFPTR_PARAM_SETTING_VALUE)
                    elif setting_type == IFptr.LIBFPTR_ST_BOOL:
                        setting_value = self.fptr.getParamBool(IFptr.LIBFPTR_PARAM_SETTING_VALUE)
                    elif setting_type == IFptr.LIBFPTR_ST_STRING:
                        setting_value = self.fptr.getParamString(IFptr.LIBFPTR_PARAM_SETTING_VALUE)
                    else:
                        setting_value = None

                    settings.append({
                        "setting_id": setting_id,
                        "setting_type": setting_type,
                        "setting_name": setting_name,
                        "setting_value": setting_value
                    })

                    self.fptr.setParam(IFptr.LIBFPTR_PARAM_RECORDS_ID, records_id)

                # Завершаем чтение
                self.fptr.setParam(IFptr.LIBFPTR_PARAM_RECORDS_ID, records_id)
                self._check_result(self.fptr.endReadRecords(), "завершения чтения настроек")

                response['success'] = True
                response['message'] = f"Прочитано настроек ККТ: {len(settings)}"
                response['data'] = {"settings": settings}

            elif command == 'read_last_document_journal':
                # Читаем последний закрытый документ из электронного журнала
                self._check_result(self.fptr.getLastDocumentJournal(), "чтения последнего документа из журнала")

                # Получаем TLV-массив
                tlv_list = self.fptr.getParamByteArray(IFptr.LIBFPTR_PARAM_TLV_LIST)

                # Парсим TLV-структуры
                tlv_structures = []
                pos = 0
                while pos < len(tlv_list):
                    if pos + 4 > len(tlv_list):
                        break

                    # Читаем Tag (2 байта, LE)
                    tag = tlv_list[pos] | (tlv_list[pos + 1] << 8)
                    # Читаем Length (2 байта, LE)
                    length = tlv_list[pos + 2] | (tlv_list[pos + 3] << 8)
                    pos += 4

                    # Читаем Value
                    if pos + length > len(tlv_list):
                        break

                    value = list(tlv_list[pos:pos + length])
                    pos += length

                    tlv_structures.append({
                        "tag": tag,
                        "length": length,
                        "value": value
                    })

                response['success'] = True
                response['message'] = f"Последний документ из журнала успешно прочитан, TLV структур: {len(tlv_structures)}"
                response['data'] = {
                    "tlv_structures": tlv_structures,
                    "raw_bytes": list(tlv_list)
                }

            # ======================================================================
            # FN Query Data Commands (Запрос информации из ФН)
            # ======================================================================
            elif command == 'query_last_receipt':
                # Запрос информации о последнем чеке из ФН
                self.fptr.setParam(IFptr.LIBFPTR_PARAM_FN_DATA_TYPE, IFptr.LIBFPTR_FNDT_LAST_RECEIPT)
                self._check_result(self.fptr.fnQueryData(), "запроса информации о последнем чеке")

                # Получаем данные о последнем чеке
                document_number = self.fptr.getParamInt(IFptr.LIBFPTR_PARAM_DOCUMENT_NUMBER)
                receipt_sum = self.fptr.getParamDouble(IFptr.LIBFPTR_PARAM_RECEIPT_SUM)
                fiscal_sign = self.fptr.getParamString(IFptr.LIBFPTR_PARAM_FISCAL_SIGN)
                date_time = self.fptr.getParamDateTime(IFptr.LIBFPTR_PARAM_DATE_TIME)
                receipt_type = self.fptr.getParamInt(IFptr.LIBFPTR_PARAM_RECEIPT_TYPE)

                # Определяем название типа чека
                receipt_type_names = {
                    IFptr.LIBFPTR_RT_SELL: "Чек прихода",
                    IFptr.LIBFPTR_RT_SELL_RETURN: "Чек возврата прихода",
                    IFptr.LIBFPTR_RT_SELL_CORRECTION: "Чек коррекции прихода",
                    IFptr.LIBFPTR_RT_BUY: "Чек расхода",
                    IFptr.LIBFPTR_RT_BUY_RETURN: "Чек возврата расхода",
                    IFptr.LIBFPTR_RT_BUY_CORRECTION: "Чек коррекции расхода",
                }
                receipt_type_name = receipt_type_names.get(receipt_type, f"Неизвестный тип ({receipt_type})")

                response['success'] = True
                response['message'] = f"Информация о последнем чеке (№{document_number}) успешно получена"
                response['data'] = {
                    "document_number": document_number,
                    "receipt_sum": receipt_sum,
                    "fiscal_sign": fiscal_sign,
                    "date_time": date_time.strftime("%Y-%m-%d %H:%M:%S") if date_time else None,
                    "receipt_type": receipt_type,
                    "receipt_type_name": receipt_type_name
                }

            elif command == 'query_registration_info':
                # Запрос регистрационных данных ККТ
                self.fptr.setParam(IFptr.LIBFPTR_PARAM_FN_DATA_TYPE, IFptr.LIBFPTR_FNDT_REG_INFO)
                self._check_result(self.fptr.fnQueryData(), "запроса регистрационных данных")

                # Получаем все регистрационные данные
                data = {}

                # Строковые параметры
                data['fns_url'] = self.fptr.getParamString(1060)  # Адрес сайта ФНС
                data['organization_address'] = self.fptr.getParamString(1009)  # Адрес расчетов
                data['organization_vatin'] = self.fptr.getParamString(1018)  # ИНН пользователя
                data['organization_name'] = self.fptr.getParamString(1048)  # Наименование пользователя
                data['organization_email'] = self.fptr.getParamString(1117)  # Email отправителя чека
                data['payments_address'] = self.fptr.getParamString(1187)  # Место расчетов
                data['registration_number'] = self.fptr.getParamString(1037)  # Регистрационный номер ККТ
                data['machine_number'] = self.fptr.getParamString(1036)  # Номер автомата
                data['ofd_vatin'] = self.fptr.getParamString(1017)  # ИНН ОФД
                data['ofd_name'] = self.fptr.getParamString(1046)  # Название ОФД

                # Числовые параметры
                taxation_types = self.fptr.getParamInt(1062)  # Системы налогообложения (битовое поле)
                agent_sign = self.fptr.getParamInt(1057)  # Признак агента (битовое поле)
                ffd_version = self.fptr.getParamInt(1209)  # Номер версии ФФД

                # Преобразуем системы налогообложения в список
                taxation_systems = []
                if taxation_types & IFptr.LIBFPTR_TT_OSN:
                    taxation_systems.append("Общая")
                if taxation_types & IFptr.LIBFPTR_TT_USN_INCOME:
                    taxation_systems.append("УСН доход")
                if taxation_types & IFptr.LIBFPTR_TT_USN_INCOME_OUTCOME:
                    taxation_systems.append("УСН доход минус расход")
                if taxation_types & IFptr.LIBFPTR_TT_ESN:
                    taxation_systems.append("ЕСХН")
                if taxation_types & IFptr.LIBFPTR_TT_PATENT:
                    taxation_systems.append("Патентная")
                data['taxation_systems'] = taxation_systems

                # Преобразуем признак агента
                agent_types = []
                if agent_sign == 0:
                    agent_types.append("Признак агента отсутствует")
                else:
                    if agent_sign & IFptr.LIBFPTR_AT_BANK_PAYING_AGENT:
                        agent_types.append("Банковский платежный агент")
                    if agent_sign & IFptr.LIBFPTR_AT_BANK_PAYING_SUBAGENT:
                        agent_types.append("Банковский платежный субагент")
                    if agent_sign & IFptr.LIBFPTR_AT_PAYING_AGENT:
                        agent_types.append("Платежный агент")
                    if agent_sign & IFptr.LIBFPTR_AT_PAYING_SUBAGENT:
                        agent_types.append("Платежный субагент")
                    if agent_sign & IFptr.LIBFPTR_AT_ATTORNEY:
                        agent_types.append("Поверенный")
                    if agent_sign & IFptr.LIBFPTR_AT_COMMISSION_AGENT:
                        agent_types.append("Комиссионер")
                    if agent_sign & IFptr.LIBFPTR_AT_ANOTHER:
                        agent_types.append("Другой тип агента")
                data['agent_types'] = agent_types

                # Преобразуем версию ФФД
                ffd_versions = {
                    IFptr.LIBFPTR_FFD_UNKNOWN: "Неизвестная",
                    IFptr.LIBFPTR_FFD_1_05: "ФФД 1.05",
                    IFptr.LIBFPTR_FFD_1_1: "ФФД 1.1",
                    IFptr.LIBFPTR_FFD_1_2: "ФФД 1.2",
                }
                data['ffd_version'] = ffd_versions.get(ffd_version, f"Неизвестная ({ffd_version})")
                data['ffd_version_code'] = ffd_version

                # Булевы параметры
                data['auto_mode_sign'] = self.fptr.getParamBool(1001)  # Признак автоматического режима
                data['offline_mode_sign'] = self.fptr.getParamBool(1002)  # Признак автономного режима
                data['encryption_sign'] = self.fptr.getParamBool(1056)  # Признак шифрования
                data['internet_sign'] = self.fptr.getParamBool(1108)  # Признак ККТ для расчетов в сети Интернет
                data['service_sign'] = self.fptr.getParamBool(1109)  # Признак расчетов за услуги
                data['bso_sign'] = self.fptr.getParamBool(1110)  # Признак АС БСО

                # Дополнительные признаки (могут быть недоступны на старых ФФД)
                try:
                    data['lottery_sign'] = self.fptr.getParamBool(1126)  # Признак проведения лотерей
                    data['gambling_sign'] = self.fptr.getParamBool(1193)  # Признак проведения азартных игр
                    data['excise_sign'] = self.fptr.getParamBool(1207)  # Признак подакцизного товара
                    data['machine_installation_sign'] = self.fptr.getParamBool(1221)  # Признак установки принтера в автомате
                except:
                    pass  # Эти поля могут отсутствовать

                # Дополнительные параметры через именованные константы
                try:
                    data['trade_marked_products'] = self.fptr.getParamBool(IFptr.LIBFPTR_PARAM_TRADE_MARKED_PRODUCTS)
                    data['insurance_activity'] = self.fptr.getParamBool(IFptr.LIBFPTR_PARAM_INSURANCE_ACTIVITY)
                    data['pawn_shop_activity'] = self.fptr.getParamBool(IFptr.LIBFPTR_PARAM_PAWN_SHOP_ACTIVITY)
                    data['vending'] = self.fptr.getParamBool(IFptr.LIBFPTR_PARAM_VENDING)
                    data['catering'] = self.fptr.getParamBool(IFptr.LIBFPTR_PARAM_CATERING)
                    data['wholesale'] = self.fptr.getParamBool(IFptr.LIBFPTR_PARAM_WHOLESALE)
                except:
                    pass  # Эти поля могут отсутствовать

                response['success'] = True
                response['message'] = "Регистрационные данные ККТ успешно получены"
                response['data'] = data

            elif command == 'query_fn_info':
                # Запрос информации и статуса ФН
                self.fptr.setParam(IFptr.LIBFPTR_PARAM_FN_DATA_TYPE, IFptr.LIBFPTR_FNDT_FN_INFO)
                self._check_result(self.fptr.fnQueryData(), "запроса информации о ФН")

                data = {
                    'fn_serial': self.fptr.getParamString(IFptr.LIBFPTR_PARAM_SERIAL_NUMBER),
                    'fn_version': self.fptr.getParamString(IFptr.LIBFPTR_PARAM_FN_VERSION),
                }

                # Исполнение ФН (только для ФН-М)
                try:
                    data['fn_execution'] = self.fptr.getParamString(IFptr.LIBFPTR_PARAM_FN_EXECUTION)
                except:
                    pass

                # Тип ФН
                fn_type = self.fptr.getParamInt(IFptr.LIBFPTR_PARAM_FN_TYPE)
                fn_types = {
                    IFptr.LIBFPTR_FNT_UNKNOWN: "Неизвестный",
                    IFptr.LIBFPTR_FNT_DEBUG: "Отладочная версия",
                    IFptr.LIBFPTR_FNT_RELEASE: "Боевая версия"
                }
                data['fn_type'] = fn_types.get(fn_type, f"Неизвестный ({fn_type})")
                data['fn_type_code'] = fn_type

                # Состояние ФН
                fn_state = self.fptr.getParamInt(IFptr.LIBFPTR_PARAM_FN_STATE)
                fn_states = {
                    IFptr.LIBFPTR_FNS_INITIAL: "Настройка ФН",
                    IFptr.LIBFPTR_FNS_CONFIGURED: "Готовность к активации",
                    IFptr.LIBFPTR_FNS_FISCAL_MODE: "Фискальный режим",
                    IFptr.LIBFPTR_FNS_POSTFISCAL_MODE: "Постфискальный режим",
                    IFptr.LIBFPTR_FNS_ACCESS_ARCHIVE: "Доступ к архиву"
                }
                data['fn_state'] = fn_states.get(fn_state, f"Неизвестное ({fn_state})")
                data['fn_state_code'] = fn_state

                # Флаги и статусы
                data['fn_flags'] = self.fptr.getParamInt(IFptr.LIBFPTR_PARAM_FN_FLAGS)
                data['fn_need_replacement'] = self.fptr.getParamBool(IFptr.LIBFPTR_PARAM_FN_NEED_REPLACEMENT)
                data['fn_resource_exhausted'] = self.fptr.getParamBool(IFptr.LIBFPTR_PARAM_FN_RESOURCE_EXHAUSTED)
                data['fn_memory_overflow'] = self.fptr.getParamBool(IFptr.LIBFPTR_PARAM_FN_MEMORY_OVERFLOW)
                data['fn_ofd_timeout'] = self.fptr.getParamBool(IFptr.LIBFPTR_PARAM_FN_OFD_TIMEOUT)
                data['fn_critical_error'] = self.fptr.getParamBool(IFptr.LIBFPTR_PARAM_FN_CRITICAL_ERROR)

                # URI сервера ОКП
                fn_contains_uri = self.fptr.getParamBool(IFptr.LIBFPTR_PARAM_FN_CONTAINS_KEYS_UPDATER_SERVER_URI)
                data['fn_contains_keys_updater_server_uri'] = fn_contains_uri
                if fn_contains_uri:
                    data['fn_keys_updater_server_uri'] = self.fptr.getParamString(IFptr.LIBFPTR_PARAM_FN_KEYS_UPDATER_SERVER_URI)

                response['success'] = True
                response['message'] = "Информация о ФН успешно получена"
                response['data'] = data

            elif command == 'query_ofd_exchange_status':
                # Запрос статуса информационного обмена с ОФД
                self.fptr.setParam(IFptr.LIBFPTR_PARAM_FN_DATA_TYPE, IFptr.LIBFPTR_FNDT_OFD_EXCHANGE_STATUS)
                self._check_result(self.fptr.fnQueryData(), "запроса статуса обмена с ОФД")

                exchange_status = self.fptr.getParamInt(IFptr.LIBFPTR_PARAM_OFD_EXCHANGE_STATUS)

                # Расшифровываем битовое поле статуса
                status_flags = []
                if exchange_status & (1 << 0):
                    status_flags.append("Транспортное соединение установлено")
                if exchange_status & (1 << 1):
                    status_flags.append("Есть сообщение для передачи в ОФД")
                if exchange_status & (1 << 2):
                    status_flags.append("Ожидание ответного сообщения (квитанции) от ОФД")
                if exchange_status & (1 << 3):
                    status_flags.append("Есть команда от ОФД")
                if exchange_status & (1 << 4):
                    status_flags.append("Изменились настройки соединения с ОФД")
                if exchange_status & (1 << 5):
                    status_flags.append("Ожидание ответа на команду от ОФД")

                date_time = self.fptr.getParamDateTime(IFptr.LIBFPTR_PARAM_DATE_TIME)
                okp_time = self.fptr.getParamDateTime(IFptr.LIBFPTR_PARAM_LAST_SUCCESSFUL_OKP)

                data = {
                    'exchange_status_code': exchange_status,
                    'exchange_status_flags': status_flags,
                    'unsent_documents_count': self.fptr.getParamInt(IFptr.LIBFPTR_PARAM_DOCUMENTS_COUNT),
                    'first_unsent_document_number': self.fptr.getParamInt(IFptr.LIBFPTR_PARAM_DOCUMENT_NUMBER),
                    'ofd_message_read': self.fptr.getParamBool(IFptr.LIBFPTR_PARAM_OFD_MESSAGE_READ),
                    'first_unsent_date_time': date_time.strftime("%Y-%m-%d %H:%M:%S") if date_time else None,
                    'last_successful_okp_time': okp_time.strftime("%Y-%m-%d %H:%M:%S") if okp_time else None,
                }

                response['success'] = True
                response['message'] = "Статус обмена с ОФД успешно получен"
                response['data'] = data

            elif command == 'query_shift_info':
                # Запрос информации о текущей смене в ФН
                self.fptr.setParam(IFptr.LIBFPTR_PARAM_FN_DATA_TYPE, IFptr.LIBFPTR_FNDT_SHIFT)
                self._check_result(self.fptr.fnQueryData(), "запроса информации о смене")

                data = {
                    'receipts_count': self.fptr.getParamInt(IFptr.LIBFPTR_PARAM_RECEIPT_NUMBER),
                    'shift_number': self.fptr.getParamInt(IFptr.LIBFPTR_PARAM_SHIFT_NUMBER),
                }

                response['success'] = True
                response['message'] = "Информация о смене успешно получена"
                response['data'] = data

            elif command == 'query_last_document':
                # Запрос информации о последнем фискальном документе
                self.fptr.setParam(IFptr.LIBFPTR_PARAM_FN_DATA_TYPE, IFptr.LIBFPTR_FNDT_LAST_DOCUMENT)
                self._check_result(self.fptr.fnQueryData(), "запроса информации о последнем документе")

                date_time = self.fptr.getParamDateTime(IFptr.LIBFPTR_PARAM_DATE_TIME)

                data = {
                    'document_number': self.fptr.getParamInt(IFptr.LIBFPTR_PARAM_DOCUMENT_NUMBER),
                    'fiscal_sign': self.fptr.getParamString(IFptr.LIBFPTR_PARAM_FISCAL_SIGN),
                    'date_time': date_time.strftime("%Y-%m-%d %H:%M:%S") if date_time else None,
                }

                response['success'] = True
                response['message'] = "Информация о последнем документе успешно получена"
                response['data'] = data

            elif command == 'query_fn_validity':
                # Запрос срока действия ФН
                self.fptr.setParam(IFptr.LIBFPTR_PARAM_FN_DATA_TYPE, IFptr.LIBFPTR_FNDT_VALIDITY)
                self._check_result(self.fptr.fnQueryData(), "запроса срока действия ФН")

                date_time = self.fptr.getParamDateTime(IFptr.LIBFPTR_PARAM_DATE_TIME)

                data = {
                    'validity_date': date_time.strftime("%Y-%m-%d") if date_time else None,
                    'registrations_count': self.fptr.getParamInt(IFptr.LIBFPTR_PARAM_REGISTRATIONS_COUNT),
                    'registrations_remain': self.fptr.getParamInt(IFptr.LIBFPTR_PARAM_REGISTRATIONS_REMAIN),
                }

                response['success'] = True
                response['message'] = "Срок действия ФН успешно получен"
                response['data'] = data

            else:
                response['message'] = f"Неизвестная команда: {command}"

        except Exception as e:
            error_msg = f"Ошибка при выполнении команды '{command}': {str(e)}"
            logger.error(error_msg)
            response["message"] = error_msg
            if isinstance(e, AtolDriverError):
                response['data'] = e.to_dict()

        return response

class DeviceWorker:
    """Воркер для конкретного фискального регистратора"""

    def __init__(self, device_id: str, device_config: dict):
        """
        Инициализация воркера для устройства

        Args:
            device_id: Идентификатор устройства
            device_config: Конфигурация устройства
        """
        self.device_id = device_id
        self.device_config = device_config
        self.processor = None  # Будет создан при первом использовании
        self.command_channel = f"command_fr_channel_{device_id}"
        self.response_channel = f"command_fr_channel_{device_id}_response"

        logger.info(f"✓ Воркер для устройства '{device_id}' инициализирован")
        logger.info(f"  - Канал команд: {self.command_channel}")
        logger.info(f"  - Канал ответов: {self.response_channel}")

    def _get_processor(self, redis_client=None):
        """Получить или создать процессор команд (lazy initialization)"""
        if self.processor is None:
            self.processor = CommandProcessor(redis_client=redis_client)
            logger.info(f"[{self.device_id}] Создан процессор команд")
        return self.processor

    def process_message(self, r: redis.Redis, message: dict):
        """Обработка сообщения из канала"""
        if message.get('type') == 'message':
            if message.get('data') == 'ping':
                return

            try:
                command_data = json.loads(message.get('data'))
                logger.debug(f"[{self.device_id}] Получена команда: {command_data}")

                # Используем lazy initialization для процессора, передаем redis клиент
                processor = self._get_processor(redis_client=r)
                response = processor.process_command(command_data)
                r.publish(self.response_channel, json.dumps(response, ensure_ascii=False))
                logger.debug(f"[{self.device_id}] Ответ отправлен: {response}")

            except json.JSONDecodeError as e:
                logger.error(f"[{self.device_id}] Ошибка парсинга команды: {e}")
            except Exception as e:
                logger.error(f"[{self.device_id}] Неожиданная ошибка: {e}")


def get_device_configs() -> Dict[str, dict]:
    """
    Получить конфигурации всех устройств из переменных окружения

    Формат переменных:
    DEVICES=device1,device2,device3
    DEVICE_device1_TYPE=tcp
    DEVICE_device1_HOST=192.168.1.100
    DEVICE_device1_PORT=5555
    """
    import os

    devices = {}
    devices_list = os.getenv('DEVICES', 'default').split(',')

    for device_id in devices_list:
        device_id = device_id.strip()
        prefix = f"DEVICE_{device_id}_"

        # Получаем конфигурацию устройства из переменных окружения
        device_config = {
            'connection_type': os.getenv(f"{prefix}TYPE", settings.atol_connection_type),
            'host': os.getenv(f"{prefix}HOST", settings.atol_host),
            'port': int(os.getenv(f"{prefix}PORT", settings.atol_port)),
        }

        devices[device_id] = device_config
        logger.info(f"Загружена конфигурация для устройства '{device_id}': {device_config}")

    return devices


def listen_to_redis():
    """Подключение к Redis и обработка команд от всех устройств"""
    r = redis.Redis(host=settings.redis_host, port=settings.redis_port, decode_responses=True)
    pubsub = r.pubsub()

    # Загружаем конфигурацию устройств
    device_configs = get_device_configs()

    # Создаем воркеров для каждого устройства
    workers = {}
    for device_id, device_config in device_configs.items():
        worker = DeviceWorker(device_id, device_config)
        workers[device_id] = worker
        pubsub.subscribe(worker.command_channel)

    logger.info(f"🎧 Ожидание команд от {len(workers)} устройств...")

    # Обрабатываем сообщения из всех каналов
    for message in pubsub.listen():
        # Определяем, какому устройству предназначено сообщение
        channel = message.get('channel')
        if channel:
            for device_id, worker in workers.items():
                if channel == worker.command_channel:
                    worker.process_message(r, message)
                    break


if __name__ == "__main__":
    logger.info("🚀 Запуск Multi-Device Redis Queue Worker для АТОЛ ККТ")
    listen_to_redis()