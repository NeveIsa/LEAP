import marimo

__generated_with = "0.14.13"
app = marimo.App(width="medium")


@app.cell
def _():
    return


@app.cell
def _():
    import duckdb

    # Connect to the DuckDB database in read-only mode
    conn = duckdb.connect(database='students.db', read_only=True)

    try:
        # Example query to fetch data from a table named 'students'
        query = "SELECT * FROM students;"
        _result = conn.execute(query).fetchall()
    finally:
        # Close the connection
        conn.close()

    # Display the result
    _result

    return


@app.cell
def _():
    return


if __name__ == "__main__":
    app.run()
