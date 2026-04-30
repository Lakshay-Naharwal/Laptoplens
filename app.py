from flask import Flask, render_template, request, jsonify
import pickle
import pandas as pd
import os

app = Flask(__name__)

# Load model and metadata
script_dir = os.path.dirname(os.path.abspath(__file__))
model_path = os.path.join(script_dir, "model", "laptop_price_model.pkl")
metadata_path = os.path.join(script_dir, "model", "metadata.pkl")

try:
    with open(model_path, "rb") as f:
        model = pickle.load(f)
    with open(metadata_path, "rb") as f:
        metadata = pickle.load(f)
except Exception as e:
    print(f"Error loading model/metadata: {e}")
    model = None
    metadata = None


@app.route("/")
def index():
    if not metadata:
        return (
            "Model and metadata not found. Please train the model first by running train_model.py.",
            500,
        )

    # Sort categories for better UI experience
    sorted_categories = {}
    for col, cats in metadata["categories"].items():
        # Handle nan values by converting to string or filtering
        clean_cats = [str(c) for c in cats if str(c).lower() != "nan"]
        sorted_categories[col] = sorted(clean_cats)

    return render_template(
        "index.html", metadata=metadata, sorted_categories=sorted_categories
    )


@app.route("/predict", methods=["POST"])
def predict():
    if not model or not metadata:
        return jsonify({"error": "Model not loaded"}), 500

    try:
        data = request.json
        inputs = {}

        # Process categorical inputs
        for col in metadata["categorical_cols"]:
            inputs[col] = data.get(col, "")

        # Process numerical inputs
        for col in metadata["numerical_cols"]:
            val = data.get(col, "")
            try:
                inputs[col] = float(val) if val != "" else 0.0
            except ValueError:
                inputs[col] = 0.0

        input_df = pd.DataFrame([inputs])

        # Get prediction
        prediction = model.predict(input_df)[0]
        prediction_val = float(prediction)

        # Ensure prediction is non-negative
        if prediction_val < 0:
            prediction_val = 0.0

        return jsonify(
            {
                "success": True,
                "prediction": prediction_val,
                "formatted_prediction": f"₹{prediction_val:,.2f}",
            }
        )
    except Exception as e:
        import traceback

        traceback.print_exc()
        return jsonify({"error": str(e)}), 400


if __name__ == "__main__":
    app.run(debug=True, port=5000)
