import hmac
import hashlib


order_id = "order_SiG0V82tKFpbd6"

payment_id = "pay_test_003"

secret = "8Nzj84kcNu3tP8WmNhsT3Etd"

data = f"{order_id}|{payment_id}"
# HMAC SHA256 hashing logic
signature = hmac.new(
    secret.encode(),
    data.encode(),
    hashlib.sha256
).hexdigest()

print("\n" + "="*30)
print(f"RAZORPAY ORDER ID:  {order_id}")
print(f"PAYMENT ID:        {payment_id}")
print(f"GENERATED SIGNATURE: \n{signature}")
print("="*30 + "\n")