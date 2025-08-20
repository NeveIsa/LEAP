import marimo

__generated_with = "0.14.16"
app = marimo.App(width="medium")


@app.cell
def _():
    import requests as req

    import seaborn as sns

    return req, sns


@app.cell
def _(req):
    logs = req.get("http://localhost:9000/logs?sid=s001&exp=eigen").json()["logs"]
    return (logs,)


@app.function
def transform(logs):
    x,y = [],[]
    for log in logs:
        xx = log["result_json"][0]
        yy = log["result_json"][1]
        x.append(xx)
        y.append(yy)
    return x,y


@app.cell
def _(logs):
    x,y = transform(logs)
    return x, y


@app.cell
def _(sns, x, y):
    sns.scatterplot(x=x,y=y)
    return


@app.cell
def _():
    return


if __name__ == "__main__":
    app.run()
