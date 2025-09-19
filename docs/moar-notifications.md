# MORE NOTIFICATIONS!! MOAR!!!11

- 현재는 카드 교환이 이루어져도 알림이 뜨지 않으니 앱을 기동하는 일이 적다
- 카드 교환이 되고, FULLY REVEAL이 되면 알림을 띄워주자!

- 그런데 카드 교환 횟수가 많으면, 그만큼 알림이 여러개가 한번에 뜰 수 있으니까, 오후 7시쯤 맞춰서 `send_notification(...) if user.discovered_cards.filter(date=today).exists()` 같은 느낌으로 가자
