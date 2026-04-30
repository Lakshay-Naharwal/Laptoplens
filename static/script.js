document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('prediction-form');
    const submitBtn = document.getElementById('submit-btn');
    const btnText = document.querySelector('.btn-text');
    const spinner = document.getElementById('loading-spinner');
    
    const priceDisplay = document.querySelector('.price-display');
    const amountSpan = document.getElementById('predicted-price');
    const confidenceText = document.querySelector('.confidence-text');
    const instructionText = document.querySelector('.instruction-text');

    // Function to animate numbers
    function animateValue(obj, start, end, duration) {
        let startTimestamp = null;
        const step = (timestamp) => {
            if (!startTimestamp) startTimestamp = timestamp;
            const progress = Math.min((timestamp - startTimestamp) / duration, 1);
            
            // Ease out cubic
            const easeProgress = 1 - Math.pow(1 - progress, 3);
            
            const currentVal = start + (end - start) * easeProgress;
            
            // Format number with commas and 2 decimal places
            obj.innerHTML = currentVal.toLocaleString('en-IN', {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2
            });
            
            if (progress < 1) {
                window.requestAnimationFrame(step);
            } else {
                // Ensure final value is exact
                obj.innerHTML = end.toLocaleString('en-IN', {
                    minimumFractionDigits: 2,
                    maximumFractionDigits: 2
                });
            }
        };
        window.requestAnimationFrame(step);
    }

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        // UI State: Loading
        submitBtn.disabled = true;
        btnText.style.display = 'none';
        spinner.style.display = 'block';
        
        // Gather form data
        const formData = new FormData(form);
        const data = {};
        formData.forEach((value, key) => {
            data[key] = value;
        });

        try {
            // Send request to Flask backend
            const response = await fetch('/predict', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(data)
            });

            const result = await response.json();

            if (result.success) {
                // Hide instructions
                instructionText.style.display = 'none';
                
                // Show result container with animation
                priceDisplay.classList.remove('active');
                confidenceText.classList.remove('active');
                
                // Small delay to reset animation state if predicting multiple times
                setTimeout(() => {
                    priceDisplay.classList.add('active');
                    confidenceText.classList.add('active');
                    
                    // Animate number from 0 to prediction
                    const targetPrice = parseFloat(result.prediction);
                    animateValue(amountSpan, 0, targetPrice, 1500);
                }, 50);

            } else {
                alert('Error making prediction: ' + result.error);
            }
        } catch (error) {
            console.error('Error:', error);
            alert('Failed to connect to the server. Please try again later.');
        } finally {
            // UI State: Reset
            submitBtn.disabled = false;
            btnText.style.display = 'block';
            spinner.style.display = 'none';
        }
    });

    // Add subtle hover animations to inputs
    const inputs = document.querySelectorAll('input, select');
    inputs.forEach(input => {
        input.addEventListener('focus', () => {
            input.parentElement.parentElement.style.transform = 'translateX(5px)';
            input.parentElement.parentElement.style.transition = 'transform 0.3s ease';
        });
        
        input.addEventListener('blur', () => {
            input.parentElement.parentElement.style.transform = 'translateX(0)';
        });
    });
});
