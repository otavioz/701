import html
import calendar
from collections import defaultdict
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, List, Optional

from consts import DATABASE
from src.database import DatabaseManager
from src.utils import get_users


class MonthClosingNotFound(ValueError):
    """Raised when a monthly report is requested before any closing is recorded."""


class BillReceiptBot:
    def __init__(self, db: Optional[DatabaseManager] = None):
        self.db = db or DatabaseManager(DATABASE)

    def monthly_summary(self, now: Optional[datetime] = None) -> List[str]:
        now = now or datetime.now()
        closing_date = self.db.get_latest_month_closing(now)
        if closing_date is None:
            raise MonthClosingNotFound(
                "Nenhum fechamento registrado. Use /fechamento para iniciar o período."
            )

        products_by_owner: Dict[str, list] = defaultdict(list)
        for product in self.db.get_all_products():
            if closing_date < product.created_at <= now:
                products_by_owner[product.owner].append(product)

        pix_transactions = [
            pix for pix in self.db.get_all_pix()
            if closing_date < pix.include_date <= now
        ]

        lines = [
            "<b>Resumo do mês</b>",
            f"Período: após {closing_date.strftime('%d/%m/%Y %H:%M')} até "
            f"{now.strftime('%d/%m/%Y %H:%M')}",
            "",
            "<b>Produtos por responsável</b>",
        ]

        product_total = 0.0
        if products_by_owner:
            for owner in sorted(products_by_owner, key=str.casefold):
                products = products_by_owner[owner]
                owner_total = sum(product.price for product in products)
                product_total += owner_total
                lines.append(f"<b>{html.escape(str(owner))}</b>")
                for product in products:
                    name = html.escape(str(product.product_name))
                    quantity = html.escape(f"{product.quantity:g}")
                    unity = html.escape(str(product.unity))
                    lines.append(
                        f"• {name} — {quantity} {unity}: R$ {product.price:.2f}"
                    )
                lines.append(f"Subtotal: R$ {owner_total:.2f}")
        else:
            lines.append("Nenhum produto incluído no período.")
        lines.append(f"<b>Total de produtos: R$ {product_total:.2f}</b>")

        pix_total = sum(pix.value for pix in pix_transactions)
        lines.extend(["", "<b>PIX</b>"])
        if pix_transactions:
            for pix in sorted(pix_transactions, key=lambda item: item.include_date):
                sender = html.escape(str(pix.from_))
                receiver = html.escape(str(pix.to_))
                included_at = pix.include_date.strftime("%d/%m/%Y %H:%M")
                lines.append(
                    f"• from: {sender} | to: {receiver} | "
                    f"value: R$ {pix.value:.2f} | include date: {included_at}"
                )
        else:
            lines.append("Nenhum PIX incluído no período.")
        lines.append(f"<b>Total de PIX: R$ {pix_total:.2f}</b>")

        return self._split_message(lines)

    def close_month(self, reference_month: int, reference_year: int) -> List[str]:
        if not 1 <= reference_month <= 12:
            raise ValueError("O mês deve estar entre 1 e 12.")
        if reference_year < 1:
            raise ValueError("O ano informado é inválido.")

        period_start = datetime(reference_year, reference_month, 1)
        period_end = datetime(
            reference_year,
            reference_month,
            calendar.monthrange(reference_year, reference_month)[1],
            23, 59, 59, 999999,
        )
        products = [
            product for product in self.db.get_all_products()
            if period_start <= product.date <= period_end
        ]
        pix_transactions = [
            pix for pix in self.db.get_all_pix()
            if period_start <= pix.date_ <= period_end
        ]

        residents = [
            user['nome'] for user in get_users()
            if user['user_type'] == 1
        ]
        if not residents:
            raise ValueError("Não há usuários moradores (user_type 1) cadastrados.")

        amounts_due = {resident: 0 for resident in residents}
        for product in products:
            amount_cents = self._to_cents(product.price)
            base_share, remainder = divmod(amount_cents, len(residents))
            owner = str(product.owner).strip().casefold()
            for index, resident in enumerate(residents):
                share = base_share + (index < remainder)
                if owner != resident.strip().casefold():
                    amounts_due[resident] += share

        pix_paid: Dict[str, int] = defaultdict(int)
        for pix in pix_transactions:
            pix_paid[str(pix.from_)] += self._to_cents(pix.value)

        month_names = (
            "janeiro", "fevereiro", "março", "abril", "maio", "junho",
            "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
        )
        recalculating = self.db.get_month_closing(reference_month, reference_year)
        lines = [
            f"<b>Fechamento do Mês de "
            f"{month_names[reference_month - 1].capitalize()}/{reference_year}</b>",
        ]
        if recalculating is not None:
            lines.append("<b>RECALCULO do mês já informado</b>")
        lines.extend([
            f"Total de Compras: R$ "
            f"{self._from_cents(sum(self._to_cents(product.price) for product in products)):.2f}",
        ])

        final_by_residents = {}
        for resident in residents:
            amount_due = amounts_due[resident] - pix_paid.get(resident, 0)
            final_by_residents[resident] = amount_due
            lines.append(
                f"Valor para {html.escape(resident)}: "
                f"R$ {self._from_cents(amount_due):.2f}"
            )

        total_products = sum(
            self._to_cents(product.price) for product in products
        )
        total_transactions = sum(
            self._to_cents(pix.value) for pix in pix_transactions
        )
        self.db.create_month_closing(
            closing_date=datetime.now(),
            reference_month=reference_month,
            reference_year=reference_year,
            total_products=float(self._from_cents(total_products)),
            total_transactions=float(self._from_cents(total_transactions)),
            total_by_residents={
                resident: float(self._from_cents(final_by_residents[resident]))
                for resident in residents
            },
        )
        return self._split_message(lines)

    @staticmethod
    def _to_cents(value: float) -> int:
        amount = Decimal(str(value)).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        return int(amount * 100)

    @staticmethod
    def _from_cents(value: int) -> Decimal:
        return Decimal(value) / 100

    @staticmethod
    def _split_message(lines: List[str], limit: int = 3800) -> List[str]:
        messages = []
        current = ""
        for line in lines:
            candidate = f"{current}\n{line}" if current else line
            if len(candidate) > limit and current:
                messages.append(current)
                current = line
            else:
                current = candidate
        if current:
            messages.append(current)
        return messages
