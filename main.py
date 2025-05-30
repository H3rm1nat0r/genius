import configparser
import logging
import traceback
from typing import List
import hdbcli.dbapi
from model import ValidationObject
from validate_IBAN import validate_IBAN
from validate_URL import validate_URL
from validate_VAT_ID import validate_VAT_ID


def main():
    """
    Main function to process classifications and validate objects.

    Establishes a connection to the HANA database, retrieves classifications,
    validates objects based on their classification, and updates the objects
    back into the database.
    """
    try:
        connection = get_connection()
        classifications = get_classifications(connection)
        CLASS_MAPPING = {
            "URL": validate_URL,
            "IBAN": validate_IBAN,
            "VAT_ID": validate_VAT_ID,
        }

        config = configparser.ConfigParser()
        config.read("config.ini")
        batching = config["batching"]
        history = batching.getint("history")

        # run fast validations first (e.g. regex checks. etc.)
        while True:
            batchsize = batching.getint("batchsize_fast")
            final = {classification: False for classification in classifications}
            for classification in classifications:
                objects = get_objects(
                    connection, classification, batchsize, history, "fast"
                )
                if len(objects) == 0:
                    final[classification] = True
                    continue
                logging.info(f"Classification: {classification}")
                if classification in CLASS_MAPPING:
                    validator = CLASS_MAPPING[classification]()
                    validated_objects = validator.validate_fast(objects)
                    update_objects(connection, validated_objects)
                    logging.info(
                        f"Updated {len(validated_objects)} objects in database."
                    )
                else:
                    logging.warning(
                        f"No validator found for classification: {classification}"
                    )
            if all(final.values()):
                break

        # run slow validations now (e.g. external api calls etc.)
        while True:
            batchsize = batching.getint("batchsize_slow")
            final = {classification: False for classification in classifications}
            for classification in classifications:
                objects = get_objects(
                    connection, classification, batchsize, history, "slow"
                )
                if len(objects) == 0:
                    final[classification] = True
                    continue
                logging.info(f"Classification: {classification}")
                if classification in CLASS_MAPPING:
                    validator = CLASS_MAPPING[classification]()
                    validated_objects = validator.validate_slow(objects)
                    if validated_objects is None or len(validated_objects) == 0:
                        continue
                    update_objects(connection, validated_objects)
                    logging.info(
                        f"Updated {len(validated_objects)} objects in database."
                    )
                else:
                    logging.warning(
                        f"No validator found for classification: {classification}"
                    )
            if all(final.values()):
                break

    except hdbcli.dbapi.Error as e:
        logging.error(f"hdbcli.dbapi.Error: {e}")
        traceback.print_exc()  # Print the stack trace for hdbcli.dbapi.Error
    except Exception as e:
        logging.error(f"Exception: {e}")
        traceback.print_exc()  # Print the stack trace for general exceptions
        raise Exception(e)
    else:
        logging.info("Finished processing all classifications.")

    finally:
        # Close connection
        if connection:
            connection.close()


def get_connection():
    """
    Establishes a connection to the HANA database using configuration details from 'config.ini'.

    Reads the HANA database connection details such as address, port, user, and password from the 'hana' section
    of the 'config.ini' file and uses these details to establish a connection to the database.

    Returns:
        hdbcli.dbapi.Connection: A connection object to the HANA database.

    Raises:
        configparser.NoSectionError: If the 'hana' section is not found in the 'config.ini' file.
        configparser.NoOptionError: If any of the required options (address, port, user, password) are missing in the 'hana' section.
        hdbcli.dbapi.Error: If there is an error connecting to the HANA database.
    """
    config = configparser.ConfigParser()
    config.read("config.ini")

    hana_config = config["hana"]
    address = hana_config["address"]
    port = hana_config.getint("port")
    user = hana_config["user"]
    password = hana_config["password"]

    # Connect to the HANA database
    connection = hdbcli.dbapi.connect(
        address=address, port=port, user=user, password=password
    )

    return connection


def get_classifications(connection):
    """
    Retrieve distinct classifications from the GENIUS.SHARED_NAIGENT_DATA table.

    Args:
        connection (object): A database connection object.

    Returns:
        list: A list of tuples containing distinct classifications.
    """
    # Execute SQL query
    cursor = connection.cursor()
    cursor.execute(
        """
    SELECT DISTINCT CLASSIFICATION
    FROM GENIUS.SHARED_NAIGENT_DATA
"""
    )

    # Fetch results
    classifications = cursor.fetchall()
    return [classification[0] for classification in classifications]


def get_objects(
    connection, classification, batchsize, history, mode
) -> List[ValidationObject]:
    """
    Retrieve objects from the GENIUS.SHARED_NAIGENT_DATA table based on the classification.

    Args:
        connection (object): A database connection object.
        classification (str): The classification to filter the objects.

    Returns:
        list: A list of tuples containing objects based on the classification.
    """
    # Execute SQL query
    query = f"""
SELECT DISTINCT
      CLASSIFICATION
    , VALUE
    , STATUS
    , STATUS_MESSAGE
    , LAST_VISITED
    , ADDITIONAL_INFORMATION
FROM
	GENIUS.SHARED_NAIGENT_DATA 
WHERE
	CLASSIFICATION = '{classification}'"""
    if mode == "fast":
        query += f"""
AND (LAST_VISITED IS NULL
	OR LAST_VISITED < ADD_DAYS(CURRENT_DATE,{history}))"""
    elif mode == "slow":
        query += f"""
AND STATUS = 'formal ok'"""
    query += f"""        
ORDER BY 
	COALESCE(LAST_VISITED,'2000-01-01') ASC
	, VALUE ASC
LIMIT {batchsize}
	"""
    logging.debug(f"Query: {query}")
    cursor = connection.cursor()
    cursor.execute(query)

    # Fetch results
    objects = cursor.fetchall()
    return [
        ValidationObject(
            classification=object[0],
            value=object[1],
            status=object[2],
            status_message=object[3],
            last_visited=None,
            additional_information=object[5],
        )
        for object in objects
    ]


def update_objects(connection, objects: List[ValidationObject]):
    """
    Update the validated objects back into the GENIUS.SHARED_NAIGENT_DATA table.

    Args:
        connection (object): A database connection object.
        objects (List[ValidationObject]): A list of validated objects to be updated.
    """
    cursor = connection.cursor()
    query = """
        UPDATE GENIUS.SHARED_NAIGENT_DATA
        SET STATUS = ?, STATUS_MESSAGE = ?, LAST_VISITED = ?, ADDITIONAL_INFORMATION = ?
        WHERE CLASSIFICATION = ? AND VALUE = ?
    """

    params = [
        (
            obj.status,
            obj.status_message,
            obj.last_visited,
            obj.additional_information,
            obj.classification,
            obj.value,
        )
        for obj in objects
        if obj.last_visited is not None
    ]

    cursor.executemany(query, params)
    connection.commit()


logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
main()
