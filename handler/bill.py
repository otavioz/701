import html
import calendar
from collections import defaultdict
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, List, Optional

from consts import DATABASE, HOUSE_ACCOUNT_OWNER
from src.database import DatabaseManager
from src.utils import find_user_name, get_users


class MonthClosingNotFound(ValueError):
    """Raised when a monthly report is requested before any closing is recorded."""


class BillReceiptBot:
    def __init__(self, db: Optional[DatabaseManager] = None):
        self.db = db or DatabaseManager(DATABASE)

    def monthly_summary(
        self,
        reference_month: Optional[int] = None,
        reference_year: Optional[int] = None,
        now: Optional[datetime] = None,
    ) -> List[str]:
        now = now or datetime.now()
        if reference_month is None and reference_year is None:
            reference_month, reference_year = now.month, now.year
        elif reference_month is None or reference_year is None:
            raise ValueError("Informe mês e ano juntos.")
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

        products_by_owner: Dict[str, list] = defaultdict(list)
        for product in self.db.get_all_products():
            if period_start <= product.date <= period_end:
                products_by_owner[product.owner].append(product)

        pix_transactions = [
            pix for pix in self.db.get_all_pix()
            if period_start <= pix.date_ <= period_end
        ]

        lines = [
            f"<b>Resumo de {reference_month:02d}/{reference_year}</b>",
            f"Período: {period_start.strftime('%d/%m/%Y %H:%M')} a "
            f"{period_end.strftime('%d/%m/%Y %H:%M')}",
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
            lines.append("Nenhum produto encontrado no período.")
        lines.append(f"<b>Total de produtos: R$ {product_total:.2f}</b>")

        pix_total = sum(pix.value for pix in pix_transactions)
        lines.extend(["", "<b>PIX</b>"])
        if pix_transactions:
            for pix in sorted(pix_transactions, key=lambda item: item.date_):
                sender = html.escape(str(pix.from_))
                receiver = html.escape(str(pix.to_))
                included_at = pix.include_date.strftime("%d/%m/%Y %H:%M")
                lines.append(
                    f"• from: {sender} | to: {receiver} | "
                    f"value: R$ {pix.value:.2f} | include date: {included_at}"
                )
        else:
            lines.append("Nenhum PIX encontrado no período.")
        lines.append(f"<b>Total de PIX: R$ {pix_total:.2f}</b>")

        return self._split_message(lines)

    def accounts_summary(self, now: Optional[datetime] = None) -> List[str]:
        now = now or datetime.now()
        period_start = datetime(now.year, now.month, 1)
        period_end = datetime(
            now.year,
            now.month,
            calendar.monthrange(now.year, now.month)[1],
            23, 59, 59, 999999,
        )
        transactions = sorted(
            (
                pix for pix in self.db.get_all_pix()
                if period_start <= pix.date_ <= period_end
            ),
            key=lambda pix: pix.date_,
        )
        bill_totals, total_for_house, savings, per_resident = (
            self._summarize_bill_transactions(transactions)
        )
        month_names = (
            "janeiro", "fevereiro", "março", "abril", "maio", "junho",
            "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
        )
        lines = [
            f"<b>Resumo de contas de "
            f"{month_names[now.month - 1].capitalize()}/{now.year}</b>",
        ]
        for name, amount in bill_totals.items():
            lines.append(
                f"{html.escape(name)}: "
                f"R$ {self._from_cents(amount):.2f}"
            )
        lines.extend([
            f"Total para casa: R$ {self._from_cents(total_for_house):.2f}",
            f"Valor Poupança: R$ {self._from_cents(savings):.2f}",
            f"Valor para cada: R$ {self._from_cents(per_resident):.2f}",
            "",
            "<b>Transações</b>",
        ])
        if transactions:
            for pix in transactions:
                lines.extend([
                    f"De {html.escape(str(pix.from_))} "
                    f"para {html.escape(str(pix.to_))}",
                    f"Valor: R$ {pix.value:.2f}",
                    f"Banco: {html.escape(str(pix.bank_))}",
                    f"Data: {pix.date_.strftime('%d/%m/%Y %H:%M:%S')}",
                    "",
                ])
        else:
            lines.append("Nenhuma transação encontrada neste mês.")
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
        bill_totals, total_for_house, savings, per_resident = (
            self._summarize_bill_transactions(pix_transactions)
        )

        residents = [
            user['nome'] for user in get_users()
            if user['user_type'] == 1
        ]
        if not residents:
            raise ValueError("Não há usuários moradores (user_type 1) cadastrados.")

        amounts_due = {resident: 0 for resident in residents}
        purchases_by_residents = {resident: 0 for resident in residents}
        resident_names = {resident.casefold(): resident for resident in residents}
        house_products = []
        house_products_total = 0
        total_products = 0
        for product in products:
            amount_cents = self._to_cents(product.price)
            owner = str(product.owner).strip().casefold()
            resident_owner = resident_names.get(owner)
            if resident_owner is None:
                #house_products.append({
                #    'product_name': product.product_name,
                #    'owner': product.owner,
                #    'value': float(self._from_cents(amount_cents)),
                #})
                house_products_total += amount_cents
            else:
                purchases_by_residents[resident_owner] += amount_cents
            total_products += amount_cents


        payments_by_residents: Dict[str, int] = defaultdict(int)
        resident_names = {resident.casefold(): resident for resident in residents}
        for pix in pix_transactions:
            receiver = str(pix.to_).strip().casefold()
            sender = resident_names.get(str(pix.from_).strip().casefold())
            if receiver == HOUSE_ACCOUNT_OWNER.casefold() and sender is not None:
                payments_by_residents[sender] += self._to_cents(pix.value)

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
            lines.append("<i>Mês fechado, recalculo realizado.</i>\n")
        for name, amount in bill_totals.items():
            lines.append(
                f"{html.escape(name)}: R$ {self._from_cents(amount):.2f}"
            )
        lines.extend([
            f"Valor Poupança: R$ {self._from_cents(savings):.2f}",
            f"Total da casa: R$ {self._from_cents(total_for_house):.2f}",
            f"Total para cada: R$ {self._from_cents(per_resident):.2f}",
            "",
            "<b>Compras</b>",
            f"Total de Compras: R$ "
            f"{self._from_cents(total_products):.2f}",
        ])

        final_by_residents = {}
        for resident in residents:
            lines.append(
                f"Feitas por {html.escape(resident)}: "
                f"R$ {self._from_cents(purchases_by_residents[resident]):.2f}"
            )
        lines.append(
            f"Outros: R$ "
            f"{self._from_cents(house_products_total):.2f}"
        )

        for resident in residents:
            amount_due = total_products/len(residents) - purchases_by_residents.get(resident, 0)
            final_by_residents[resident] = amount_due
            lines.append(
                f"Valor a pagar por {html.escape(resident)}: "
                f"R$ {self._from_cents(amount_due):.2f}"
            )

        lines.append("")
        lines.append("<b>Pagamentos</b>")
        for resident in residents:
            lines.append(
                f"{html.escape(resident)}: "
                f"R$ {self._from_cents(payments_by_residents.get(resident, 0)):.2f}"
            )

        total_products = sum(
            self._to_cents(product.price) for product in products
        )
        total_transactions = total_for_house
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
            bills_by_recipient={
                name: float(self._from_cents(amount))
                for name, amount in bill_totals.items()
            },
            total_house=float(self._from_cents(total_for_house)),
            valor_poupanca=float(self._from_cents(savings)),
            total_per_resident=float(self._from_cents(per_resident)),
            purchases_by_residents={
                resident: float(self._from_cents(purchases_by_residents[resident]))
                for resident in residents
            },
            house_products_total=float(self._from_cents(house_products_total)),
            payments_by_residents={
                resident: float(self._from_cents(payments_by_residents.get(resident, 0)))
                for resident in residents
            },
        )
        return self._split_message(lines)

    def _summarize_bill_transactions(self, transactions):
        bill_recipients = get_users(user_type=2)
        residents = get_users(user_type=1)
        totals_by_recipient = {user['nome']: 0 for user in bill_recipients}

        for pix in transactions:
            recipient_name = find_user_name(str(pix.to_), bill_recipients)
            if recipient_name is not None:
                totals_by_recipient[recipient_name] += self._to_cents(pix.value)

        total_for_house = sum(totals_by_recipient.values())
        savings = self._to_cents(
            self._from_cents(total_for_house) * Decimal("0.10")
        )
        per_resident = (
            self._to_cents(
                self._from_cents(total_for_house + savings) / len(residents)
            )
            if residents else 0
        )
        return totals_by_recipient, total_for_house, savings, per_resident

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
