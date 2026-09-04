"""Calendario de sesiones de mercado -- abstracción que permite a
_split_contiguous() (score.py) distinguir un hueco de calendario real de
una simple ausencia de sesión esperada (fin de semana, festivo bursátil).

Motivo (2026-09-04, Bloque 4): cripto cotiza 24/7 -- CUALQUIER día
ausente en la serie es una anomalía real (ver XRP: Coinbase lo deslistó
~905 días por el litigio SEC-Ripple, un hueco genuino). Las acciones
cotizan solo en sesiones NYSE/NASDAQ (lunes-viernes, excepto festivos)
-- un viernes->lunes es la operativa normal, NO un hueco de datos.

Deliberadamente NO es una regla arbitraria tipo "más de 3 días" (eso
ocultaría huecos reales de varios días en cripto, y fallaría en
semanas con un festivo bursátil de más -- ej. Acción de Gracias +
fin de semana da un salto de 4 días naturales que una regla de umbral
fijo no distinguiría de un día de sesión realmente ausente). En su
lugar, calcula cuántas sesiones de trading se esperaban entre dos
fechas dadas -- 0 sesiones esperadas es continuidad real, sin importar
cuántos días naturales haya de por medio.

Sin dependencias externas (no pandas_market_calendars, no numpy): los
festivos de NYSE son un conjunto pequeño y calculable con reglas fijas
(Computus para Viernes Santo, "n-ésimo lunes del mes" para el resto),
no una lista que haya que mantener a mano ni descargar.
"""
import datetime


def _easter_sunday(year):
    """Algoritmo de Gauss (anónimo gregoriano) -- válido para el
    calendario gregoriano, sin dependencias externas ni tablas."""
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return datetime.date(year, month, day)


def _nth_weekday_of_month(year, month, weekday, n):
    """weekday: 0=lunes ... 6=domingo. n-ésima ocurrencia (1-indexado)."""
    d = datetime.date(year, month, 1)
    offset = (weekday - d.weekday()) % 7
    return d + datetime.timedelta(days=offset + 7 * (n - 1))


def _last_weekday_of_month(year, month, weekday):
    if month == 12:
        d = datetime.date(year + 1, 1, 1) - datetime.timedelta(days=1)
    else:
        d = datetime.date(year, month + 1, 1) - datetime.timedelta(days=1)
    offset = (d.weekday() - weekday) % 7
    return d - datetime.timedelta(days=offset)


def _observed(date):
    """NYSE: festivo en sábado se observa el viernes anterior; en
    domingo, el lunes siguiente."""
    if date.weekday() == 5:
        return date - datetime.timedelta(days=1)
    if date.weekday() == 6:
        return date + datetime.timedelta(days=1)
    return date


def us_market_holidays(year):
    """Festivos NYSE de un año -- reglas fijas, sin lista mantenida a
    mano. Juneteenth es festivo NYSE desde 2022, no se incluye antes."""
    holidays = {
        _observed(datetime.date(year, 1, 1)),               # Año Nuevo
        _nth_weekday_of_month(year, 1, 0, 3),                # MLK Day (3er lunes de enero)
        _nth_weekday_of_month(year, 2, 0, 3),                # Presidents' Day (3er lunes de febrero)
        _easter_sunday(year) - datetime.timedelta(days=2),   # Viernes Santo
        _last_weekday_of_month(year, 5, 0),                  # Memorial Day (último lunes de mayo)
        _observed(datetime.date(year, 7, 4)),                # Independence Day
        _nth_weekday_of_month(year, 9, 0, 1),                # Labor Day (1er lunes de septiembre)
        _nth_weekday_of_month(year, 11, 3, 4),               # Thanksgiving (4º jueves de noviembre)
        _observed(datetime.date(year, 12, 25)),              # Navidad
    }
    if year >= 2022:
        holidays.add(_observed(datetime.date(year, 6, 19)))  # Juneteenth
    return holidays


def is_trading_day(date, asset_type):
    """asset_type='crypto': siempre True (24/7). asset_type='equity':
    True salvo fin de semana o festivo NYSE."""
    if asset_type == "crypto":
        return True
    if date.weekday() >= 5:
        return False
    return date not in us_market_holidays(date.year)


def sessions_skipped_between(date1, date2, asset_type):
    """Número de sesiones de trading esperadas ESTRICTAMENTE entre
    date1 y date2 (exclusive-exclusive) sin dato. 0 significa
    "continuo": date2 es la siguiente sesión real tras date1, no falta
    nada esperado en medio -- ni un fin de semana ni un festivo bursátil
    cuentan como sesión esperada."""
    n = 0
    d = date1 + datetime.timedelta(days=1)
    while d < date2:
        if is_trading_day(d, asset_type):
            n += 1
        d += datetime.timedelta(days=1)
    return n
