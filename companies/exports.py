import csv

from django.http import HttpResponse


def csv_response(filename, header, rows):
    """Réponse CSV compatible Excel français (séparateur « ; », encodage UTF-8 avec BOM)."""
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response.write("﻿")
    writer = csv.writer(response, delimiter=";")
    writer.writerow(header)
    for row in rows:
        writer.writerow(row)
    return response
