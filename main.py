import pickle
import pandas as pd
import numpy as np

def load_resources():
    with open('model/laptop_price_model.pkl', 'rb') as f:
        model = pickle.load(f)
    with open('model/metadata.pkl', 'rb') as f:
        metadata = pickle.load(f)
    return model, metadata

def get_user_input(metadata):
    print("\n--- Laptop Price Prediction ---")
    print("Please enter the following details:")
    
    inputs = {}
    
    # Simple helper to handle choice inputs
    def get_choice(prompt, options):
        print(f"\n{prompt}")
        # Sort options for easier finding, but keep them unique
        sorted_options = sorted([str(opt) for opt in options])
        # Show first 10 if too many
        if len(sorted_options) > 15:
            print("Common options:", ", ".join(sorted_options[:15]), "...")
        else:
            print("Options:", ", ".join(sorted_options))
            
        while True:
            val = input("Enter value: ").strip()
            if val in options:
                return val
            # Loose matching
            matches = [opt for opt in options if val.lower() in str(opt).lower()]
            if len(matches) == 1:
                confirm = input(f"Did you mean '{matches[0]}'? (y/n): ")
                if confirm.lower() == 'y':
                    return matches[0]
            print(f"Invalid input. Please choose from the available options.")

    # Categorical Inputs
    for col in metadata['categorical_cols']:
        inputs[col] = get_choice(f"Select {col}:", metadata['categories'][col])
        
    # Numerical Inputs
    for col in metadata['numerical_cols']:
        while True:
            try:
                val = input(f"Enter {col} (numeric): ").strip()
                inputs[col] = float(val)
                break
            except ValueError:
                print("Please enter a valid number.")
                
    return pd.DataFrame([inputs])

def main():
    try:
        model, metadata = load_resources()
    except FileNotFoundError:
        print("Model files not found. Please run train_model.py first.")
        return

    input_df = get_user_input(metadata)
    
    prediction = model.predict(input_df)[0]
    
    print("\n" + "="*30)
    print(f"Predicted Price: ₹{prediction:,.2f}")
    print("="*30 + "\n")

if __name__ == "__main__":
    main()
