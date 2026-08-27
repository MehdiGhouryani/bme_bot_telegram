# src/bme_bot/db/equipment_connection.py
#
# اتصال مستقل و async-safe به medical_device.db (محتوای آموزشی تجهیزات، جدول
# information). این دیتابیس عمداً کاملاً از users.db جدا می‌ماند و از طریق
# یک ماژول اتصال اختصاصی (این فایل) در دسترس قرار می‌گیرد.
#
# نکته‌ی امنیتی: کوئری‌های واقعی روی جدول information در equipment_repository.py
# نوشته می‌شوند، نه اینجا؛ این ماژول فقط مسئول باز/بسته‌کردن اتصال است تا مسئولیت‌ها
# از هم جدا بمانند.
#
# get_connection از _connection_factory.py می‌آید تا کد باز/بستن اتصال با
# app_connection.py تکرار نشود؛ خودِ دیتابیس همچنان کاملاً جدا و مستقل است.

from ._connection_factory import make_connection_getter
from .. import config

get_connection = make_connection_getter(lambda: config.EQUIPMENT_DB_PATH)
