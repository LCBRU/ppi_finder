#!/usr/bin/env python

import argparse
import csv
import re
from datetime import datetime, date
from dateutil.parser import parse
from dateutil.relativedelta import relativedelta


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('inputfile', nargs=1)
    
    args = parser.parse_args()

    with open(args.inputfile[0], newline='') as csvfile:
        reader = csv.DictReader(csvfile)

        ppif = PpiFinder()

        result = ppif.analyse(reader)

    report = ''
    for c, r in result.items():
        report += found_message(c, 'UHL System Number', r)
        report += found_message(c, 'postcode', r)
        report += found_message(c, 'NHS Number', r)
        report += found_message(c, 'Date of Birth', r)
        if len(r['Name']) > 0:
            report += f'Column "{c}" may contain the names: {", ".join(r["Name"])}\n'

    print(report)

def found_message(column, ppi_name, result):
    values = result[ppi_name]

    if values is not None:
        return f'Column "{column}" may contain a {ppi_name} first found in row {values["row"]} in value {values["value"]}\n'
    else:
        return ''

class PpiFinder():
    re_numbers = re.compile(r'\d')
    re_words = re.compile(r'\W+')
    re_uhl_s_number = re.compile(r'([SRFG]\d{7}|[U]\d{7}.*|LB\d{7}|RTD[\-0-9]*)')
    re_postcodes = re.compile(r'([Gg][Ii][Rr] ?0[Aa]{2})|((([A-Za-z][0-9]{1,2})|(([A-Za-z][A-Ha-hJ-Yj-y][0-9]{1,2})|(([A-Za-z][0-9][A-Za-z])|([A-Za-z][A-Ha-hJ-Yj-y][0-9][A-Za-z]?))))\s?[0-9][A-Za-z]{2})')
    re_nhs_dividers = re.compile(r'[- ]')
    re_nhs_numbers = re.compile(r'(?=(\d{10}))')
    re_ansi_dates = re.compile(r'(?P<year>\d{4})[\\ -]?(?P<month>\d{2})[\\ -]?(?P<day>\d{2})(?:[ T]\d{2}:\d{2}:\d{2})?(?:\.\d+)?(?:[+-]\d{2}:\d{2})?')


    def __init__(self):
        with open('_names.txt', 'r') as f:
            self.names = {n for n in f.readlines()}

    def analyse(self, csv):

        errors = {c: {
            'UHL System Number': None,
            'postcode': None,
            'NHS Number': None,
            'Date of Birth': None,
            'Name': set(),
        } for c in csv.fieldnames}

        for i, row in enumerate(csv):
            if i % 1000 == 0:
                print(f"Analysed {i:,} rows")

            for c in csv.fieldnames:
                value = row[c]
                e = errors[c]

                if e['UHL System Number'] is None:
                    if self.contains_uhl_system_number(value):
                        e['UHL System Number'] = {'row': i, 'value': value}
                if e['postcode'] is None:
                    if self.contains_postcode(value):
                        e['postcode'] = {'row': i, 'value': value}
                if e['NHS Number'] is None:
                    if self.contains_nhs_number(value):
                        e['NHS Number'] = {'row': i, 'value': value}
                if e['Date of Birth'] is None:
                    if self.contains_dob(value):
                        e['Date of Birth'] = {'row': i, 'value': value}
                e['Name'].update(self.contains_name(value))

        return errors

    def contains_name(self, value):
        if not value or not isinstance(value, str):
            return set()

        value = self.re_numbers.sub(' ', value.lower())

        found = set()

        for w in self.re_words.split(value):
            if w in self.names:
                found.add(w)

        return found

    def contains_uhl_system_number(self, value):
        if not value or not isinstance(value, str):
            return False

        if self.re_uhl_s_number.search(value):
            return True

    def contains_postcode(self, value):
        if not value or not isinstance(value, str):
            return False

        if self.re_postcodes.search(value):
            return True

    def contains_nhs_number(self, value):
        if not value:
            return False

        if isinstance(value, str):
            value = self.re_nhs_dividers.sub('', value)
        else:
            value = str(value)

        # A valid NHS number must be 10 digits long
        matches = self.re_nhs_numbers.findall(value)

        for m in matches:
            if self.calculate_nhs_number_checksum(m) == m[9]:
                return True

    def contains_dob(self, value):
        try:
            dt_val = self.parse_date(value)
        except:
            return False

        if not dt_val:
            return False

        if (datetime.utcnow().date() - relativedelta(years=130)) < dt_val < (datetime.utcnow().date() - relativedelta(years=10)):
            return True

    def calculate_nhs_number_checksum(self, nhs_number):
        checkcalc = lambda sum: 11 - (sum % 11)

        char_total = sum(
            [int(j) * (11 - (i + 1)) for i, j in enumerate(nhs_number[:9])]
        )
        return str(checkcalc(char_total)) if checkcalc(char_total) != 11 else '0'

    def parse_date(self, value):
        if not value:
            return None

        if isinstance(value, datetime):
            return value.date()

        if isinstance(value, date):
            return value

        value = str(value)

        ansi_match = self.re_ansi_dates.fullmatch(value)

        if ansi_match:
            return date(
                int(ansi_match.group('year')),
                int(ansi_match.group('month')),
                int(ansi_match.group('day')),
            )

        try:
            f = float(value)
            if not (1_000_000 < f < 100_000_000):
                return None
        except:
            pass


        parsed_date = parse(value, dayfirst=True)

        return parsed_date.date()


if __name__ == "__main__":
   main()