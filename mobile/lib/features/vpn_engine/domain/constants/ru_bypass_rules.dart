class RuBypassRules {
  /// Android package names for Russian banking, state and marketplace apps
  static const Set<String> androidPackages = {
    'ru.sberbankmobile',           // СберБанк Онлайн
    'com.idamob.tinkoff.android',  // Т-Банк
    'ru.vtb24.mobilebanking',      // ВТБ
    'ru.alfabank.mobile.android',  // Альфа-Банк
    'ru.rostel',                   // Госуслуги
    'com.wildberries.ru',          // Wildberries
    'ru.ozon.app.android',         // Ozon
    'ru.yandex.market',            // Яндекс Маркет
    'ru.nspk.mirpay',              // Mir Pay
    'ru.tinkoff.investing',        // Т-Инвестиции
  };

  /// Domain list for DNS-based split tunneling (iOS & desktop)
  static const Set<String> domains = {
    'gosuslugi.ru',
    'sberbank.ru',
    'sber.ru',
    'tbank.ru',
    'tinkoff.ru',
    'vtb.ru',
    'alfabank.ru',
    'wildberries.ru',
    'wb.ru',
    'ozon.ru',
    'ya.ru',
    'yandex.ru',
    'mos.ru',
    'nalog.gov.ru',
    'nspk.ru',
    'cbr.ru',
  };
}
