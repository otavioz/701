from datetime import datetime
import logging
import os
import re
from typing import Dict, Optional
import uuid

from consts import MONTH_MAP, TRANSFERS_DIR
from src.utils import get_users
FILEHEADER = 'from;to;value;institution;code;date;include_date;fix;reference_year;reference_month'

class Pix():

    def __init__(self, from_: str = None, to_: str = None, value: float = 0.0,
                 id_: Optional[str] = None, date_: Optional[datetime] = None,
                 bank_: str = 'N/I', correction_: bool = False,
                 reference_year: Optional[int] = None, 
                 reference_month: Optional[int] = None,
                 doc_id:Optional[int] = None):
        self.from_ = from_
        self.to_ = to_
        self.value = float(value) if value is not None else 0.0
        self.id_ = id_ or str(uuid.uuid4())[:8]
        self.date_ = date_ if date_ is not None else datetime.now()
        self.bank_ = bank_
        self.include_date = datetime.now()
        self.correction_ = correction_
        
        # New attributes
        self.reference_year = reference_year if reference_year is not None else self.date_.year
        self.reference_month = reference_month if reference_month is not None else self.date_.month

        #On reading attrs
        self.doc_id = doc_id

    def to_dict(self) -> Dict:
        """Convert Pix object to dictionary for storage."""
        return {
            'from_': self.from_,
            'to_': self.to_,
            'value': self.value,
            'id_': self.id_,
            'date_': self.date_.isoformat(),
            'bank_': self.bank_,
            'include_date': self.include_date.isoformat(),
            'correction_': self.correction_,
            'reference_year': self.reference_year,
            'reference_month': self.reference_month
        }
    
    @classmethod
    def from_dict(cls, data: Dict, doc_id: int = None) -> 'Pix':
        """Create Pix object from dictionary."""
        pix = cls(
            from_=data['from_'],
            to_=data['to_'],
            value=data['value'],
            id_=data['id_'],
            date_=datetime.fromisoformat(data['date_']) if isinstance(data['date_'], str) else data['date_'],
            bank_=data['bank_'],
            correction_=data['correction_'],
            reference_year=data.get('reference_year'),
            reference_month=data.get('reference_month'),

            doc_id = doc_id
        )
        pix.include_date = datetime.fromisoformat(data['include_date']) if isinstance(data['include_date'], str) else data['include_date']
        return pix
    
    def __str__(self) -> str:
        return f"Pix(id={self.id_}, from={self.from_}, to={self.to_}, value={self.value})"
    
    def __repr__(self) -> str:
        return self.__str__()

    def to_csv_line(self) -> str:
        """Convert to CSV line format."""
        return f'{self.from_};{self.to_};{self.value};{self.bank_};{self.id_};{self.date_.strftime("%d/%m/%Y %H:%M:%S")};{self.include_date.strftime("%d/%m/%Y %H:%M:%S")};{self.correction_};{self.reference_year};{self.reference_month}'

    __str__ = to_csv_line  # Keep the original __str__ behavior

    def set_from(self, from_):
        aux = from_.replace('Nome', '').strip()
        aux = aux.replace('Pagador', '').strip()
        users = get_users()
        for key, value in users.items():
            if aux in value:
                aux = key
                break
        return aux
    
    def set_to(self, to_):
        aux = to_.replace('Nome', '').strip()
        aux = aux.replace('Favorecido', '').strip()
        aux = aux.replace('Favoreci', '').strip()
        users = get_users()
        for key, value in users.items():
            if aux in value:
                aux = key
                break
        return aux

    def set_value(self, value_str):
        # Remove R$ symbol and any whitespace
        cleaned = re.sub(r'R\$\s*', '', value_str.strip())
        
        # Remove thousand separators (periods)
        cleaned = cleaned.replace('.', '')
        
        # Replace comma with dot for decimal separator
        cleaned = cleaned.replace(',', '.')
        
        cleaned = cleaned.replace('Valor ', '')
        # Convert to float
        try:
            return float(cleaned)
        except ValueError:
            raise ValueError(f"Cannot convert '{value_str}' to float")
    
    def get_data(self, lines) -> list[str]:
        from_ = to_ = id = id_aux = date = date_aux = value_i = ''

        in_to = True
        for index, line in enumerate(lines):
            if ('Nome' in line and in_to) or 'Favoreci' in line or 'Estabelecimento' in line:
                to_ = line
                in_to = False
            elif ('Nome' in line and not in_to) or 'Pagador' in line:
                from_ = line
            elif 'R$' in line:
                value_i = line
            elif line == 'transferência' or line == 'pagamento':
                type_ = line
                date = line
                date_aux = lines[index+1]
            elif 'Data do ' in line:
                date = line
                date_aux = lines[index+1]
            elif 'ID' in line and 'transação' in line:
                id = line
                id_aux = lines[index+1]

        if not value_i:    
            raise IndexError('Não foi possível identificar movimentação no documento enviado.')
                
        return from_, to_, value_i, id, id_aux, date, date_aux

    def correction(self):
        # The data must be checked manually later
        self.correction_ = True

    def save(self):
        with open(TRANSFERS_DIR, 'a', encoding='utf-8') as f:
            f.write('\n')
            f.write(self.to_csv_line())
        
    @staticmethod
    def which_bank(lines):
        if 'Nu Pagamentos S.A' in lines:
            return 1
        elif 'Banco Inter S.A' in lines:
            return 2
        # else:
        #    raise IndexError('Não foi possível origem do documento enviado.')

    @staticmethod
    def backup_file():
        source_file = TRANSFERS_DIR
        destination_file = TRANSFERS_DIR.replace('.csv', '_bkp.csv')
        try:
            os.replace(source_file, destination_file)
            logging.info(f"File '{source_file}' renamed to '{destination_file}' (overwritten if existed).")
            with open(source_file, 'w') as file:
                file.write(FILEHEADER)
                # file.write('\n')
        except FileNotFoundError:
            # print(f"Error: Source file '{source_file}' not found.")
            os.rename(source_file, destination_file)
        except OSError:
            raise OSError("Erro ao tentar limpar arquivo!")            
    
class NuPix(Pix):
    """Extractor specifically for NuBank Pix receipts"""
    
    def __init__(self, lines):
        super().__init__()
        from_, to_, value, id, id_aux, date, date_aux = self.get_data(lines)

        self.from_ = self.set_from(from_)
        self.to_ = self.set_to(to_)
        self.value = self.set_value(value)
        self.id_ = self.set_id(id, id_aux)
        self.date_ = self.set_date(date, date_aux)
        self.bank_ = 'NuBank'

        self.include_date = datetime.now()
        
        # Set reference year and month from the transaction date
        self.reference_year = self.date_.year
        self.reference_month = self.date_.month

    def set_id(self, id_, id_2):
        aux = id_.replace('ID da transação:', '').strip()
        if aux == '':
            aux = id_2.replace('ID da transação:', '').strip()
        return aux

    def set_date(self, _, date_string):
        # Pattern: 21JAN 2026 - 13:55:52
        # Pattern2: 22 JAN 2026 - 19:56:42

        patterns = [r'(\d{1,2})([A-Z]{3,})\s+(\d{4})\s*[-\s]+\s*(\d{1,2}):(\d{2}):(\d{2})'
                   , r'(\d{1,2})\s([A-Z]{3,})\s+(\d{4})\s*[-\s]+\s*(\d{1,2}):(\d{2}):(\d{2})']
        for pattern in patterns:
            match = re.match(pattern, date_string, re.IGNORECASE)
            if match:
                groups = match.groups()
                if len(groups) == 6:
                    day = int(groups[0])
                    month_str = groups[1].upper()
                    year = int(groups[2])
                    hour = int(groups[3])
                    minute = int(groups[4])
                    second = int(groups[5])

                    month = MONTH_MAP.get(month_str)
                    return datetime(year, month, day, hour, minute, second)
                break
        return datetime.now()
        
class InterPix(Pix):
    
    def __init__(self, lines):
        super().__init__()
        from_, to_, value, id, id_aux, date, date_aux = self.get_data(lines)

        self.from_ = self.set_from(from_)
        self.to_ = self.set_to(to_)
        self.value = self.set_value(value)
        self.id_ = self.set_id(id, id_aux)
        self.date_ = self.set_date(date, date_aux)
        self.bank_ = 'Inter'

        self.include_date = datetime.now()
        
        # Set reference year and month from the transaction date
        self.reference_year = self.date_.year
        self.reference_month = self.date_.month

    def set_id(self, id_, id_2):
        aux = id_.replace('ID da transação', '').strip()
        if aux == '':
            aux = id_2.replace('ID da transação', '').strip()
        return aux

    def set_date(self, date_date, date_hour):
        
        # Pattern: Data do pagamento Sexta, 02/01/2026
        pattern = r'\d{1,2}[/\-]\d{1,2}[/\-]\d{4}'
        match = re.search(pattern, date_date, re.IGNORECASE)
        date = match.group() if match else '01/01/1960'

        # Pattern: Horário 12:20
        pattern = r'\d{1,2}[:h]\d{2}'
        match = re.search(pattern, date_hour, re.IGNORECASE)
        hour = match.group() if match else '00:00'
        hour = hour.replace('h', ':')  # Caso padrão seja 00h00 substituir
        date_hour = date + ' ' + hour
        return datetime.strptime(date_hour, '%d/%m/%Y %H:%M')