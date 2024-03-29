## Summary
A proof of concept showing the viability of Fourier representation to be used in image steganography. Payloads are converted to binary and encoded pixel by pixel RGB bit by bit in the magnitude space (Phase space seemed too unreliable to hold any data) of the cover image after blanking out however many rows are needed. Reed-Solomon error correction is applied to try and reduce effects of noise.


![Program interface](https://i.imgur.com/pGkjz0t.png)


## File usage
| File | Usage |
|--|--|
| 1) CombinedGUI | Main program with UI |
| 2) CombinedEncode | Older encoding version |
| 3) CombinedDecode | Older decoding version  |
| 4) ConvDecoder| Take the inverse Fourier of 2 separate images of phase and magnitude that can be edited outside the program  |

The CombinedGUI is the main program and can be directly ran to present a UI allowing both encoding and decoding of images.


## Limitations
 - Only works with images of even and square resolutions e.g. (400x400)
 - Simple flat colour images can be very prone to noise, corrupting any payloads

## Corrections
 - Note that the scaling for the maximum fourier value of the image (For a normal 24bit image) should be (column_count\*row_count\*255), not (column_count\*row_count)
 - Axis with different dimensions can be achieved by: img_rgb = img_rgb.reshape(row_count,column_count\*3) instead of column_count, row_count and swapping row_count and column_count for each color channel of the lines red_fshift = (mag_image_r\*np.exp(1j\*phase_image_r)).reshape(row_count,column_count). There are no intrinsic reasons for the limitations, only coding errors for solely targeting square images


## Dependencies
Can be installed the usual way with "pip install name"
 - numpy
 - pillow
 - pypng
 - reedsolo
