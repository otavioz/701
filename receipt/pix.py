from datetime import datetime
import re

from consts import MONTH_MAP, TRANSFERS_DIR
from src.utils import get_users


class Pix():

    def __init__(self):
        self.from_ = str
        self.to_ = str
        self.value = str
        self.id_ = str
        self.date_ = datetime
        self.bank_ = 'N/I'
        self.include_date = datetime.now()
        self.correction_ = False

    def __str__(self):
        return f'{self.from_};{self.to_};{self.value};{self.bank_};{self.id_};{self.date_.strftime("%d/%m/%Y %H:%M:%S")};{self.include_date.strftime("%d/%m/%Y %H:%M:%S")};{self.correction_}'

    def set_from(self,from_):
        aux = from_.replace('Nome', '').strip()
        aux = aux.replace('Pagador', '').strip()
        users = get_users()
        for key,value in users.items():
            if aux in value:
                aux = key
                break
        return aux
    
    def set_to(self,to_):
        aux = to_.replace('Nome', '').strip()
        aux = aux.replace('Favorecido', '').strip()
        aux = aux.replace('Favoreci', '').strip()
        users = get_users()
        for key,value in users.items():
            if aux in value:
                aux = key
                break
        return aux

    def set_value(self,value_str):
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
    
    def get_data(self,lines) -> list[str]:
        from_ = to_ = id = id_aux = date = date_aux = value_i = ''

        in_to =  True
        for index,line in enumerate(lines):
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
        #The data must be checked manually later
        self.correction_ = True

    def save(self):
        with open(TRANSFERS_DIR,'a') as f:
            f.write('\n')
            f.write(str(self))
        
    @staticmethod
    def which_bank(lines):
        if 'Nu Pagamentos S.A' in lines:
            return 1
        elif 'Banco Inter S.A' in lines:
            return 2
        else:
            raise IndexError('Não foi possível origem do documento enviado.')
            
    
class NuPix(Pix):
    """Extractor specifically for NuBank Pix receipts"""
    
    def __init__(self,lines):
        super().__init__()
        from_, to_,value, id, id_aux, date, date_aux = self.get_data(lines)

        self.from_ = self.set_from(from_)
        self.to_ = self.set_to(to_)
        self.value = self.set_value(value)
        self.id_ = self.set_id(id,id_aux)
        self.date_ = self.set_date(date, date_aux)
        self.bank_ = 'NuBank'

        self.include_date = datetime.now()

    def set_id(self,id_,id_2):
        aux = id_.replace('ID da transação:','').strip()
        if aux == '':
            aux = id_2.replace('ID da transação:','').strip()
        return aux

    def set_date(self, _, date_string):
        # Pattern: 21JAN 2026 - 13:55:52
        # Pattern2: 22 JAN 2026 - 19:56:42

        patterns = [r'(\d{1,2})([A-Z]{3,})\s+(\d{4})\s*[-\s]+\s*(\d{1,2}):(\d{2}):(\d{2})'
                   ,r'(\d{1,2})\s([A-Z]{3,})\s+(\d{4})\s*[-\s]+\s*(\d{1,2}):(\d{2}):(\d{2})']
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
    
    def __init__(self,lines):
        super().__init__()
        from_, to_, value, id, id_aux, date, date_aux = self.get_data(lines)

        self.from_ = self.set_from(from_)
        self.to_ = self.set_to(to_)
        self.value = self.set_value(value)
        self.id_ = self.set_id(id,id_aux)
        self.date_ = self.set_date(date,date_aux)
        self.bank_ = 'Inter'

        self.include_date = datetime.now()

    def set_id(self,id_,id_2):
        aux = id_.replace('ID da transação','').strip()
        if aux == '':
            aux = id_2.replace('ID da transação','').strip()
        return aux

    def set_date(self,date_date,date_hour):
        
        # Pattern: Data do pagamento Sexta, 02/01/2026
        pattern = r'\d{1,2}[/\-]\d{1,2}[/\-]\d{4}'
        match = re.search(pattern, date_date, re.IGNORECASE)
        date = match.group() if match else '01/01/1960'

        # Pattern: Horário 12:20
        pattern = r'\d{1,2}[:h]\d{2}'
        match = re.search(pattern, date_hour, re.IGNORECASE)
        hour = match.group() if match else '00:00'
        date_hour = date + ' ' + hour
        return datetime.strptime(date_hour, '%d/%m/%Y %H:%M')
    
        
