import time
from PyQt5.QtWidgets import (
    QWidget, QLabel, QLineEdit, QVBoxLayout, QHBoxLayout, QFormLayout,
    QTableWidget, QTableWidgetItem, QHeaderView, QPushButton, QCheckBox,
    QRadioButton, QButtonGroup
)
from PyQt5.QtGui import QFont, QColor, QBrush
from PyQt5.QtCore import Qt, QTimer

from sound import SoundPlayer
from websocket_client import PriceWebsocketClient
from api import (
    fetch_open_positions,
    fetch_high_low_prices,
    close_position_market,
    open_new_position_market
)


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Leverage Trading Bot")
        self.setGeometry(0, 0, 1280, 400)
        self.last_price = 0
        self.last_updated_price_time = 0
        self.alert_price_above = 0
        self.alert_price_below = 0
        self.alert_above_triggered = False
        self.alert_below_triggered = False
        self.selected_side_option = 'Invert'
        self.pair_labels = {
            "XBTUSDTM": "BTC/USDT"
        }
        self.position_trackers = {}  # Dicionário para rastrear posições para fechamento automático
        self.auto_open_new_position = True  # Flag para abrir novas posições automaticamente
        self.default_leverage = 20  # Valor padrão para alavancagem
        self.default_stop_loss = -3  # Valor padrão para stop loss
        # Novas variáveis para os trailing stops
        self.trailing_stop_16_30 = 5  # Trailing stop entre 16% e 30%
        self.trailing_stop_31_50 = 8  # Trailing stop entre 31% e 50%
        self.trailing_stop_above_50 = 10  # Trailing stop acima de 50%
        self.initUI()
        self.sound_player = SoundPlayer()

        # Iniciar cliente WebSocket em uma thread separada
        self.price_ws_client = PriceWebsocketClient()
        self.price_ws_client.price_updated.connect(self.update_price_label)
        self.price_ws_client.start()
        self.sound_player.play_sound()

    def initUI(self):
        # Aplicar tema escuro
        self.setStyleSheet("""
            QWidget {
                background-color: black;
                color: white;
            }
            QLineEdit {
                background-color: #1e1e1e;
                color: white;
                border: 1px solid #444;
            }
            QTableWidget {
                background-color: #1e1e1e;
                color: white;
                gridline-color: #444;
                margin-top: 20px;
            }
            QHeaderView::section {
                background-color: #2e2e2e;
                color: white;
            }
            QTableWidget QTableCornerButton::section {
                background-color: #2e2e2e;
            }
            QLabel#priceLabel {
                font-size: 24px;
            }
            QLabel#highLowLabel {
                font-size: 14px;
            }
            QPushButton {
                background-color: #333;
                color: white;
                border: 1px solid #555;
                padding: 5px;
            }
            QPushButton:hover {
                background-color: #444;
            }
            QCheckBox::indicator {
                border: 1px solid #5a5a5a;
                background: none;
            }
            QCheckBox::indicator:checked {
                background-color: #a1a1a1;
            }
            QRadioButton::indicator {
                border: 1px solid #5a5a5a;
                border-radius: 6px;
                background: none;
            }
            QRadioButton::indicator:checked {
                background-color: #a1a1a1;
            }
        """)

        # Criar layouts
        main_layout = QVBoxLayout()

        # Layout para preço e labels High/Low
        price_layout = QHBoxLayout()

        # Label do preço
        self.price_label = QLabel("")
        self.price_label.setObjectName("priceLabel")
        self.price_label.setFont(QFont("Arial", 20))
        self.price_label.setAlignment(Qt.AlignCenter)
        price_layout.addWidget(self.price_label)

        # Layout para High e Low
        right_layout = QVBoxLayout()

        # Label High
        self.high_label = QLabel("High: $0.00")
        self.high_label.setObjectName("highLowLabel")
        self.high_label.setFont(QFont("Arial", 14))
        self.high_label.setAlignment(Qt.AlignRight)
        self.high_label.setStyleSheet("color: green;")
        right_layout.addWidget(self.high_label)

        # Label Low
        self.low_label = QLabel("Low: $0.00")
        self.low_label.setObjectName("highLowLabel")
        self.low_label.setFont(QFont("Arial", 14))
        self.low_label.setAlignment(Qt.AlignRight)
        self.low_label.setStyleSheet("color: red;")
        right_layout.addWidget(self.low_label)

        # Adicionar layout direito ao layout de preço
        price_layout.addLayout(right_layout)

        # Adicionar layout de preço ao layout principal
        main_layout.addLayout(price_layout)

        # Label de alerta (inicialmente oculto)
        self.alert_message_label = QLabel("")
        self.alert_message_label.setFont(QFont("Arial", 12))
        self.alert_message_label.setAlignment(Qt.AlignCenter)
        self.alert_message_label.setStyleSheet("color: gold;")
        self.alert_message_label.hide()
        main_layout.addWidget(self.alert_message_label)

        # Label para posições fechadas
        self.closed_positions_label = QLabel("")
        self.closed_positions_label.setFont(QFont("Arial", 12))
        self.closed_positions_label.setAlignment(Qt.AlignCenter)
        self.closed_positions_label.setStyleSheet("color: gold;")
        self.closed_positions_label.hide()
        main_layout.addWidget(self.closed_positions_label)

        # Layout para os inputs configuráveis
        config_layout = QFormLayout()

        # Alerta maior que
        alert_above_label = QLabel("Alerta de cotação acima de:")
        alert_above_label.setFont(QFont("Arial", 10))
        self.alert_entry_above = QLineEdit("0")
        self.alert_entry_above.setFont(QFont("Arial", 10))
        self.alert_entry_above.setFixedWidth(100)
        config_layout.addRow(alert_above_label, self.alert_entry_above)

        # Alerta menor que
        alert_below_label = QLabel("Alerta de cotação abaixo de:")
        alert_below_label.setFont(QFont("Arial", 10))
        self.alert_entry_below = QLineEdit("0")
        self.alert_entry_below.setFont(QFont("Arial", 10))
        self.alert_entry_below.setFixedWidth(100)
        config_layout.addRow(alert_below_label, self.alert_entry_below)

        # Input para leverage
        leverage_label = QLabel("Leverage:")
        leverage_label.setFont(QFont("Arial", 10))
        self.leverage_input = QLineEdit(str(self.default_leverage))
        self.leverage_input.setFont(QFont("Arial", 10))
        self.leverage_input.setFixedWidth(50)
        config_layout.addRow(leverage_label, self.leverage_input)

        # Input para default_stop_loss
        default_stop_loss_label = QLabel("Default Stop Loss (%):")
        default_stop_loss_label.setFont(QFont("Arial", 10))
        self.default_stop_loss_input = QLineEdit(str(self.default_stop_loss))
        self.default_stop_loss_input.setFont(QFont("Arial", 10))
        self.default_stop_loss_input.setFixedWidth(50)
        config_layout.addRow(default_stop_loss_label, self.default_stop_loss_input)

        # Inputs para os novos trailing stops
        trailing_stop_16_30_label = QLabel("Trailing stop 16%-30%:")
        trailing_stop_16_30_label.setFont(QFont("Arial", 10))
        self.trailing_stop_16_30_input = QLineEdit(str(self.trailing_stop_16_30))
        self.trailing_stop_16_30_input.setFont(QFont("Arial", 10))
        self.trailing_stop_16_30_input.setFixedWidth(50)
        config_layout.addRow(trailing_stop_16_30_label, self.trailing_stop_16_30_input)

        trailing_stop_31_50_label = QLabel("Trailing stop 31%-50%:")
        trailing_stop_31_50_label.setFont(QFont("Arial", 10))
        self.trailing_stop_31_50_input = QLineEdit(str(self.trailing_stop_31_50))
        self.trailing_stop_31_50_input.setFont(QFont("Arial", 10))
        self.trailing_stop_31_50_input.setFixedWidth(50)
        config_layout.addRow(trailing_stop_31_50_label, self.trailing_stop_31_50_input)

        trailing_stop_above_50_label = QLabel("Trailing stop acima de 50%:")
        trailing_stop_above_50_label.setFont(QFont("Arial", 10))
        self.trailing_stop_above_50_input = QLineEdit(str(self.trailing_stop_above_50))
        self.trailing_stop_above_50_input.setFont(QFont("Arial", 10))
        self.trailing_stop_above_50_input.setFixedWidth(50)
        config_layout.addRow(trailing_stop_above_50_label, self.trailing_stop_above_50_input)

        # Radiobuttons para seleção do lado
        side_label = QLabel("Tipo de posição:")
        side_label.setFont(QFont("Arial", 10))

        # Criar os botões de rádio
        self.invert_radio = QRadioButton("Invert")
        self.invert_radio.setFont(QFont("Arial", 10))
        self.invert_radio.setFixedWidth(70)
        self.invert_radio.setChecked(True)

        self.keep_invert_radio = QRadioButton("Keep/Invert")
        self.keep_invert_radio.setFont(QFont("Arial", 10))
        self.keep_invert_radio.setFixedWidth(100)

        self.keep_radio = QRadioButton("Keep")
        self.keep_radio.setFont(QFont("Arial", 10))
        self.keep_radio.setFixedWidth(70)

        self.long_radio = QRadioButton("Long")
        self.long_radio.setFont(QFont("Arial", 10))
        self.long_radio.setFixedWidth(70)

        self.short_radio = QRadioButton("Short")
        self.short_radio.setFont(QFont("Arial", 10))
        self.short_radio.setFixedWidth(70)

        # Criar um grupo de botões para os rádios
        self.side_button_group = QButtonGroup()
        self.side_button_group.addButton(self.invert_radio)
        self.side_button_group.addButton(self.keep_invert_radio)
        self.side_button_group.addButton(self.keep_radio)
        self.side_button_group.addButton(self.long_radio)
        self.side_button_group.addButton(self.short_radio)

        # Atribuir IDs aos botões
        self.side_button_group.setId(self.invert_radio, 0)
        self.side_button_group.setId(self.keep_invert_radio, 1)
        self.side_button_group.setId(self.keep_radio, 2)
        self.side_button_group.setId(self.long_radio, 3)
        self.side_button_group.setId(self.short_radio, 4)

        # Conectar o sinal de mudança de seleção
        self.side_button_group.buttonClicked.connect(self.update_side_option)

        # Layout para os botões de rádio
        side_layout = QHBoxLayout()
        side_layout.addWidget(self.invert_radio)
        side_layout.addWidget(self.keep_invert_radio)
        side_layout.addWidget(self.keep_radio)
        side_layout.addWidget(self.long_radio)
        side_layout.addWidget(self.short_radio)

        # Adicionar ao layout de configuração
        config_layout.addRow(side_label, side_layout)

        # Adicionar o layout ao layout principal
        main_layout.addLayout(config_layout)

        # Checkbox para abrir nova posição automaticamente
        self.auto_open_checkbox = QCheckBox("Abrir nova posição automaticamente")
        self.auto_open_checkbox.setFont(QFont("Arial", 10))
        self.auto_open_checkbox.setChecked(True)
        self.auto_open_checkbox.stateChanged.connect(self.toggle_auto_open)
        self.auto_open_checkbox.setStyleSheet("QCheckBox { color: white; }")
        main_layout.addWidget(self.auto_open_checkbox)

        # Tabela de posições
        self.positions_table = QTableWidget()
        self.positions_table.setRowCount(0)
        columns = ["Contract", "Amount", "Entry/Mark Price", "Liq Price", "Margin",
                   "Unrealised PnL", "Realised PnL", "Trigger", "Actions"]
        self.positions_table.setColumnCount(len(columns))
        self.positions_table.setHorizontalHeaderLabels(columns)
        header = self.positions_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Stretch)

        # Definir larguras específicas para colunas
        self.positions_table.setColumnWidth(0, 230)
        self.positions_table.setColumnWidth(1, 100)
        self.positions_table.setColumnWidth(2, 150)
        self.positions_table.setColumnWidth(3, 80)
        self.positions_table.setColumnWidth(4, 100)
        self.positions_table.setColumnWidth(5, 150)
        self.positions_table.setColumnWidth(6, 150)
        self.positions_table.setColumnWidth(7, 80)
        self.positions_table.setColumnWidth(8, 120)

        main_layout.addWidget(self.positions_table)
        self.setLayout(main_layout)

        # Configurar timers
        self.timer = QTimer()
        self.timer.timeout.connect(self.fetch_open_positions)
        self.timer.start(1000)

        self.check_alert_timer = QTimer()
        self.check_alert_timer.timeout.connect(self.check_alert_price_changes)
        self.check_alert_timer.start(500)

        self.auto_close_timer = QTimer()
        self.auto_close_timer.timeout.connect(self.check_auto_close_positions)
        self.auto_close_timer.start(1000)

        # Timer para obter preços High/Low a cada minuto
        self.high_low_timer = QTimer()
        self.high_low_timer.timeout.connect(self.fetch_high_low_prices)
        self.high_low_timer.start(60000)  # A cada 60 segundos
        self.fetch_high_low_prices()  # Busca inicial

        # Timer para verificar alterações nos parâmetros
        self.check_parameters_timer = QTimer()
        self.check_parameters_timer.timeout.connect(self.check_parameters_changes)
        self.check_parameters_timer.start(500)

    def toggle_auto_open(self, state):
        """Atualiza a flag para abrir nova posição automaticamente."""
        self.auto_open_new_position = state == Qt.Checked

    def reset_alerts(self):
        self.alert_above_triggered = False
        self.alert_below_triggered = False

    def update_side_option(self, button):
        """Atualiza a opção de lado selecionada."""
        self.selected_side_option = button.text()
        print(f"Side option selected: {self.selected_side_option}")

    def check_alert_price_changes(self):
        try:
            new_alert_price_above = float(self.alert_entry_above.text())
            new_alert_price_below = float(self.alert_entry_below.text())

            # Atualizar alerta acima
            if new_alert_price_above > 0:
                if new_alert_price_above != self.alert_price_above:
                    self.alert_price_above = new_alert_price_above
                    self.reset_alerts()
            else:
                self.alert_price_above = 0
                self.alert_above_triggered = False

            # Atualizar alerta abaixo
            if new_alert_price_below > 0:
                if new_alert_price_below != self.alert_price_below:
                    self.alert_price_below = new_alert_price_below
                    self.reset_alerts()
            else:
                self.alert_price_below = 0
                self.alert_below_triggered = False

        except ValueError:
            pass

    def check_parameters_changes(self):
        """Atualiza as variáveis default_stop_loss e trailing stops com base nos inputs."""
        try:
            new_leverage = int(self.leverage_input.text())
            new_default_stop_loss = int(self.default_stop_loss_input.text())
            new_trailing_stop_16_30 = int(self.trailing_stop_16_30_input.text())
            new_trailing_stop_31_50 = int(self.trailing_stop_31_50_input.text())
            new_trailing_stop_above_50 = int(self.trailing_stop_above_50_input.text())

            if new_leverage != self.default_leverage:
                self.default_leverage = new_leverage

            if new_default_stop_loss != self.default_stop_loss:
                self.default_stop_loss = new_default_stop_loss

            if new_trailing_stop_16_30 != self.trailing_stop_16_30:
                self.trailing_stop_16_30 = new_trailing_stop_16_30

            if new_trailing_stop_31_50 != self.trailing_stop_31_50:
                self.trailing_stop_31_50 = new_trailing_stop_31_50

            if new_trailing_stop_above_50 != self.trailing_stop_above_50:
                self.trailing_stop_above_50 = new_trailing_stop_above_50

        except ValueError:
            pass

    def fetch_open_positions(self):
        data = fetch_open_positions()
        self.update_positions_display(data)

    def fetch_high_low_prices(self):
        high_price, low_price = fetch_high_low_prices()
        if high_price is not None and low_price is not None:
            self.high_label.setText(f"High: ${high_price:,.2f}")
            self.low_label.setText(f"Low: ${low_price:,.2f}")
        else:
            self.high_label.setText("High: N/A")
            self.low_label.setText("Low: N/A")

    def update_positions_display(self, positions):
        """Atualiza o QTableWidget com os dados mais recentes das posições."""
        self.positions_table.setRowCount(0)
        current_positions_ids = set()
        for position in positions:
            row_position = self.positions_table.rowCount()
            self.positions_table.insertRow(row_position)

            # Cálculos e preparações dos dados
            avg_entry_price = position.get('avgEntryPrice', 0)
            real_leverage = position.get('realLeverage', 0)
            maint_margin = position.get('maintMargin', 0)
            if avg_entry_price != 0:
                qtd = (real_leverage * maint_margin) / avg_entry_price
            else:
                qtd = 0

            entry_mark_price = f"{avg_entry_price} / {position.get('markPrice', 0)}"

            pos_margin = position.get('posMargin', 0)
            unrealised_pnl_value = position.get('unrealisedPnl', 0)
            if pos_margin != 0:
                pnl_percent = ((unrealised_pnl_value / pos_margin) * 100)
            else:
                pnl_percent = 0.0  # Evitar divisão por zero

            unrealised_pnl = f"{unrealised_pnl_value:.2f} USDT ({pnl_percent:.2f}%)"

            contract_type = self.pair_labels.get(position.get('symbol'), position.get('symbol'))
            current_qty = position.get('currentQty', 0)
            if current_qty < 0:
                position_direction = "SHORT"
                direction_color = 'red'
                qtd = -qtd
            else:
                position_direction = "LONG"
                direction_color = 'green'

            leverage_text = f"- {int(real_leverage)}x"

            # Widget personalizado para o contrato
            contract_widget = QWidget()
            contract_layout = QHBoxLayout()
            contract_layout.setContentsMargins(0, 0, 0, 0)
            contract_layout.setSpacing(5)

            contract_label = QLabel(contract_type)
            contract_label.setStyleSheet("color: white;")

            direction_label = QLabel(position_direction)
            direction_label.setStyleSheet(f"color: {direction_color};")

            leverage_label = QLabel(leverage_text)
            leverage_label.setStyleSheet("color: white;")

            contract_layout.addWidget(contract_label)
            contract_layout.addWidget(direction_label)
            contract_layout.addWidget(leverage_label)

            contract_widget.setLayout(contract_layout)
            contract_widget.setStyleSheet("background-color: transparent;")

            liquidation_price = position.get('liquidationPrice', 'N/A')

            amount_item = QTableWidgetItem(f"{qtd:.5f} BTC")
            amount_item.setTextAlignment(Qt.AlignCenter)
            amount_item.setForeground(QBrush(QColor('white')))

            entry_mark_item = QTableWidgetItem(entry_mark_price)
            entry_mark_item.setTextAlignment(Qt.AlignCenter)
            entry_mark_item.setForeground(QBrush(QColor('white')))

            if isinstance(liquidation_price, (int, float)):
                liq_price_str = f"{liquidation_price:.2f}"
            else:
                liq_price_str = str(liquidation_price)
            liq_price_item = QTableWidgetItem(liq_price_str)
            liq_price_item.setTextAlignment(Qt.AlignCenter)
            liq_price_item.setForeground(QBrush(QColor('gold')))

            margin_item = QTableWidgetItem(f"{pos_margin:.2f} USDT")
            margin_item.setTextAlignment(Qt.AlignCenter)
            margin_item.setForeground(QBrush(QColor('white')))

            unrealised_pnl_item = QTableWidgetItem(unrealised_pnl)
            unrealised_pnl_item.setTextAlignment(Qt.AlignCenter)
            if unrealised_pnl_value > 0:
                unrealised_pnl_item.setForeground(QBrush(QColor('green')))
            else:
                unrealised_pnl_item.setForeground(QBrush(QColor('red')))

            realised_pnl_value = position.get('realisedPnl', 0)
            realised_pnl_item = QTableWidgetItem(f"{realised_pnl_value:.2f} USDT")
            realised_pnl_item.setTextAlignment(Qt.AlignCenter)
            if realised_pnl_value > 0:
                realised_pnl_item.setForeground(QBrush(QColor('green')))
            else:
                realised_pnl_item.setForeground(QBrush(QColor('red')))

            # Obter stop loss do tracker
            position_id = position.get('id')
            stop_loss_percent = self.position_trackers.get(position_id, {}).get('trigger_stop_loss_percent', self.default_stop_loss)
            stop_loss_item = QTableWidgetItem(f"{stop_loss_percent:.2f}%")
            stop_loss_item.setTextAlignment(Qt.AlignCenter)
            if stop_loss_percent < 0:
                stop_loss_item.setForeground(QBrush(QColor('red')))
            else:
                stop_loss_item.setForeground(QBrush(QColor('green')))

            # Adicionar os itens à tabela
            self.positions_table.setCellWidget(row_position, 0, contract_widget)
            self.positions_table.setItem(row_position, 1, amount_item)
            self.positions_table.setItem(row_position, 2, entry_mark_item)
            self.positions_table.setItem(row_position, 3, liq_price_item)
            self.positions_table.setItem(row_position, 4, margin_item)
            self.positions_table.setItem(row_position, 5, unrealised_pnl_item)
            self.positions_table.setItem(row_position, 6, realised_pnl_item)
            self.positions_table.setItem(row_position, 7, stop_loss_item)

            # Botões de ação
            actions_widget = QWidget()
            actions_layout = QHBoxLayout()
            actions_layout.setContentsMargins(0, 0, 0, 0)
            actions_layout.setSpacing(0)
            market_button = QPushButton("Market")
            market_button.clicked.connect(lambda checked, pos=position: self.close_position_market(pos))
            actions_layout.addWidget(market_button)
            actions_widget.setLayout(actions_layout)
            self.positions_table.setCellWidget(row_position, 8, actions_widget)

            # Rastreamento de posições para fechamento automático
            position_id = position['id']
            current_positions_ids.add(position_id)
            if position_id not in self.position_trackers:
                # Inicializar tracker para nova posição
                self.position_trackers[position_id] = {
                    'position': position,
                    'max_pnl_percent': pnl_percent if pnl_percent >= 10 else 0,
                    'trigger_stop_loss_percent': self.default_stop_loss
                }
            else:
                # Atualizar tracker existente
                tracker = self.position_trackers[position_id]
                tracker['position'] = position  # Atualizar dados da posição

        # Remover rastreadores para posições fechadas
        for pid in list(self.position_trackers.keys()):
            if pid not in current_positions_ids:
                del self.position_trackers[pid]

    def check_auto_close_positions(self):
        """Fecha automaticamente posições com base no pnl_percent."""
        positions_to_delete = []
        default_stop_loss = self.default_stop_loss  # Usar o stop loss configurado

        for tracker in self.position_trackers.values():
            position = tracker['position']
            position_id = position['id']
            pos_margin = position.get('posMargin', 1)
            unrealised_pnl = position.get('unrealisedPnl', 0)

            # Evitar divisão por zero
            if pos_margin == 0:
                continue

            # Calcular o lucro/prejuízo percentual
            pnl_percent = (unrealised_pnl / pos_margin) * 100

            print('pnls:', pnl_percent, tracker.get('max_pnl_percent', 0), tracker.get('trigger_stop_loss_percent', default_stop_loss))

            # Determinar o stop loss apropriado com base nas novas regras
            if 3 <= pnl_percent <= 6:
                calculated_stop_loss = 1
            elif 7 <= pnl_percent <= 10:
                calculated_stop_loss = 4  # Stop loss de 4% para lucros entre 7% e 10%
            elif 11 <= pnl_percent <= 15:
                calculated_stop_loss = 5  # Stop loss de 5% para lucros entre 11% e 15%
            elif 16 <= pnl_percent <= 30:
                calculated_stop_loss = pnl_percent - self.trailing_stop_16_30
            elif 31 <= pnl_percent <= 50:
                calculated_stop_loss = pnl_percent - self.trailing_stop_31_50
            elif pnl_percent > 50:
                calculated_stop_loss = pnl_percent - self.trailing_stop_above_50
            else:
                calculated_stop_loss = default_stop_loss  # Usar stop loss padrão

            # Atualizar o stop loss no tracker se for maior que o atual
            if 'trigger_stop_loss_percent' not in tracker or calculated_stop_loss > tracker['trigger_stop_loss_percent']:
                tracker['trigger_stop_loss_percent'] = calculated_stop_loss
                print('Updated trigger_stop_loss_percent:', tracker['trigger_stop_loss_percent'])

            # Atualizar o máximo lucro percentual alcançado
            if pnl_percent > tracker.get('max_pnl_percent', 0):
                tracker['max_pnl_percent'] = pnl_percent
                print('Updated max_pnl_percent:', tracker['max_pnl_percent'])

            # Verificar se o lucro percentual caiu abaixo do stop loss configurado
            if pnl_percent <= tracker['trigger_stop_loss_percent']:
                if pnl_percent >= 0:
                    # Fechar posição com lucro
                    self.close_position_market(position)
                    message = (
                        f"Posição fechada com lucro de {pnl_percent:.2f}% "
                        f"(Unrealised PnL: {unrealised_pnl:.2f} USDT) "
                        f"descontando 12% de taxas, lucro real: {pnl_percent - 12:.2f}%"
                    )
                    self.show_alert_message(message)
                else:
                    # Fechar posição com prejuízo
                    self.close_position_market(position)
                    message = (
                        f"Posição fechada com prejuízo de {pnl_percent:.2f}% "
                        f"(Unrealised PnL: {unrealised_pnl:.2f} USDT)"
                    )
                    self.show_closed_positions_message(message)

                # Se a opção estiver marcada, abrir nova posição
                if self.auto_open_new_position:
                    self.open_new_position_after_close(position)

                # Marcar para remoção
                positions_to_delete.append(position_id)
                continue

        # Remover trackers após a iteração
        for pid in positions_to_delete:
            if pid in self.position_trackers:
                del self.position_trackers[pid]

    def open_new_position_after_close(self, closed_position):
        """Abre uma nova posição automaticamente após fechar uma posição."""
        symbol = closed_position['symbol']
        current_qty = closed_position['currentQty']
        previous_side = 'buy' if current_qty > 0 else 'sell'

        # Determinar o lado com base na opção selecionada
        if self.selected_side_option == 'Invert':
            side = 'buy' if current_qty < 0 else 'sell'  # Lado oposto
        elif self.selected_side_option == 'Keep/Invert':
            side = 'buy' if current_qty < 0 else 'sell'
            # Selecionar o botão "Keep" após inverter
            self.keep_radio.setChecked(True)
        elif self.selected_side_option == 'Keep':
            side = previous_side  # Mesmo lado da posição fechada
        elif self.selected_side_option == 'Long':
            side = 'buy'  # Sempre comprar
        elif self.selected_side_option == 'Short':
            side = 'sell'  # Sempre vender
        else:
            # Padrão é inverter
            side = 'buy' if current_qty < 0 else 'sell'

        size = abs(current_qty)
        leverage = self.default_leverage  # Alavancagem padrão

        # Chamar a função para abrir nova posição
        open_new_position_market(symbol, side, size, leverage)

    def show_alert_message(self, message):
        """Exibe uma mensagem de alerta e toca um som."""
        self.alert_message_label.setText(message)
        self.alert_message_label.show()
        self.sound_player.play_sound()

    def show_closed_positions_message(self, message):
        """Exibe uma mensagem para posições fechadas."""
        self.closed_positions_label.setText(message)
        self.closed_positions_label.show()
        self.sound_player.play_sound()

    def close_position_market(self, position):
        close_position_market(position)

    def update_price_label(self, price):
        formatted_price = f"${price:,.2f}"
        self.price_label.setText(formatted_price)

        current_time = time.time()
        time_since_last_update = current_time - self.last_updated_price_time

        if time_since_last_update >= 1:
            if price > self.last_price:
                self.price_label.setStyleSheet("color: #00ff00;")
            elif price < self.last_price:
                self.price_label.setStyleSheet("color: #ff3333;")
            self.last_updated_price_time = current_time

        # Check for alerts only if the alert prices are greater than 0
        # price must be 5 digits long or more to avoid false alerts
        if self.alert_price_above > 0 and price >= self.alert_price_above and len(str(int(self.alert_price_above))) >= 5:
            if not self.alert_above_triggered:
                self.alert_above_triggered = True
                print("ALERTA: Preço acima do valor definido")
                self.sound_player.play_sound()
                # Set alert message
                self.alert_message_label.setText(f"Alerta: Preço acima de {self.alert_price_above}")
                self.alert_message_label.show()
        else:
            if self.alert_above_triggered:
                self.alert_message_label.hide()
            self.alert_above_triggered = False

        if self.alert_price_below > 0 and price <= self.alert_price_below and len(str(int(self.alert_price_below))) >= 5:
            if not self.alert_below_triggered:
                self.alert_below_triggered = True
                print("ALERTA: Preço abaixo do valor definido")
                self.sound_player.play_sound()
                # Set alert message
                self.alert_message_label.setText(f"Alerta: Preço abaixo de {self.alert_price_below}")
                self.alert_message_label.show()
        else:
            if self.alert_below_triggered:
                self.alert_message_label.hide()
            self.alert_below_triggered = False
        self.last_price = price