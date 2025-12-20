import pytest
from src.infra.address_parser import parse_address


test_cases = (
    "address,expected_city,expected_street,expected_zip",
    [
        # Quotation marks
        ('Karl-Josef-Trubin "Gasse" 9044, 19357 Helmstedt', "Helmstedt", 'Karl-Josef-Trubin "Gasse" 9044', "19357"),
        ("O'Connell Street 100A, 1010 Dublin", "Dublin", "O'Connell Street 100A", "1010"),
        # Diffrent spacing
        ("Main Street    42,  10115     Berlin", "Berlin", "Main Street 42", "10115"),
        ("  Hauptstraße 5, 80331 München  ", "München", "Hauptstraße 5", "80331"),
        ("Hauptstraße\t5,80331\tMünchen", "München", "Hauptstraße 5", "80331"),
        # No commas, considered wrong format if not \n
        ("Burgerstraße 5\n80331 München", "München", "Burgerstraße 5", "80331"),
        ("Burgerstraße 5\r80331 München", "München", "Burgerstraße 5", "80331"),
        ("Hauptstraße\t\t5\t80331\tMünchen", None, None, None),
        ("Hauptstraße 5 80331 München", None, None, None),
        ("Brightside 5 80331 New York", None, None, None),
        ("", None, None, None),
        ("Berlin", None, None, None),
        ("10115", None, None, None),
        # Too much commas, considered wrong format
        ("Big apple 5, 80331, New York", None, None, None),
        (",,,", None, None, None),
        # Numbers in cities
        ("Main Street 5, 10115 Berlin2", "Berlin2", "Main Street 5", "10115"),
        # Special characters
        ("Königstraße 12, 70173 Stuttgart", "Stuttgart", "Königstraße 12", "70173"),
        ("Main Street 5, 12345 Köln", "Köln", "Main Street 5", "12345"),
        # Zip code formats
        ("Baker Street 10, SW1A 1AA London", "London", "Baker Street 10", "SW1A 1AA"),
        ("5th Avenue 123, 10007-0001 New York", "New York", "5th Avenue 123", "10007-0001"),
        # Empty parts
        # Realistic cases
        ("Hauptstraße 9999, 80331 München", "München", "Hauptstraße 9999", "80331"),
        ("PO Box 123, 10115 Berlin", "Berlin", "PO Box 123", "10115"),
        ("Hauptstraße 10 Suite 5, 80331 München", "München", "Hauptstraße 10 Suite 5", "80331"),
        ("Central Tower, 10115 Berlin", "Berlin", "Central Tower", "10115"),
        ("Kurfürstendamm 1, 10719 Berlin-Charlottenburg", "Berlin-Charlottenburg", "Kurfürstendamm 1", "10719"),
        (
            "Straße der Internationalen Solidarität 2, 10249 Berlin",
            "Berlin",
            "Straße der Internationalen Solidarität 2",
            "10249",
        ),
    ],
)


@pytest.mark.parametrize(*test_cases)
def test_parse_address(address, expected_city, expected_street, expected_zip):
    city, street, zip_code = parse_address(address)
    assert city == expected_city
    assert street == expected_street
    assert zip_code == expected_zip
