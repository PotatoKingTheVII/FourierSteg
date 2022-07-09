import numpy as np
import png, array
from PIL import Image


####USER INPUTS####
fin_phase = open("phase.png","rb")
fin_mag = open("edited_image.png","rb")
####USER INPUTS END####



####Load each RGB channel from the image as greyscale####
pngReader_phase = png.Reader(fin_phase)
pngReader_mag = png.Reader(fin_mag)

phase_row_count, phase_column_count, phase_pngdata, phase_meta = pngReader_phase.asDirect()
phase_image_2d = np.vstack(map(np.uint16, phase_pngdata))
phase_image_2d = np.concatenate(phase_image_2d)

mag_row_count, mag_column_count, mag_pngdata, mag_meta = pngReader_mag.asDirect()
mag_image_2d = np.vstack(map(np.uint16, mag_pngdata))
mag_image_2d = np.concatenate(mag_image_2d)


#Seperate the image data into [RRR],[BBB],[GGG] instead of RGBRGBRGBRGB for seperate treatment
mag_image_r = mag_image_2d[0::3]
mag_image_g = mag_image_2d[1::3]
mag_image_b = mag_image_2d[2::3]

phase_image_r = phase_image_2d[0::3]
phase_image_g = phase_image_2d[1::3]
phase_image_b = phase_image_2d[2::3]

#Scale these values back to their originals from the compressed 16 bit image space:
mag_image_r = (phase_row_count*phase_row_count)*(mag_image_r/255)
mag_image_g = (phase_row_count*phase_row_count)*(mag_image_g/255)
mag_image_b = (phase_row_count*phase_row_count)*(mag_image_b/255)

phase_image_r = (2*np.pi*(phase_image_r/65535)) - np.pi
phase_image_g = (2*np.pi*(phase_image_g/65535)) - np.pi
phase_image_b = (2*np.pi*(phase_image_b/65535)) - np.pi

#Combine these into an array of complex numbers for each channel#
red_fshift = (mag_image_r*np.exp(1j*phase_image_r)).reshape(phase_row_count,phase_row_count)
green_fshift = (mag_image_g*np.exp(1j*phase_image_g)).reshape(phase_row_count,phase_row_count)
blue_fshift = (mag_image_b*np.exp(1j*phase_image_b)).reshape(phase_row_count,phase_row_count)


#Unshift these back to numpy order#
red_f = np.fft.ifftshift(red_fshift)
green_f = np.fft.ifftshift(green_fshift)
blue_f = np.fft.ifftshift(blue_fshift)

#Do the inverse 2D FFT to get the image pixels back
img_r_array = np.fft.ifft2(red_f)
img_g_array = np.fft.ifft2(green_f)
img_b_array = np.fft.ifft2(blue_f)


#Perform inverse FFT to get image data back
img_r_array = np.fft.ifft2(red_f)
img_g_array = np.fft.ifft2(green_f)
img_b_array = np.fft.ifft2(blue_f)

#We need to manually round each pixel and limit it's range to 0-255 here before casting to uint8
img_r_array = np.uint8(np.clip(np.round(np.abs(img_r_array.real)),0,255))
img_g_array = np.uint8(np.clip(np.round(np.abs(img_g_array.real)),0,255))
img_b_array = np.uint8(np.clip(np.round(np.abs(img_b_array.real)),0,255))

#Merge the seperate RGB channels together for the final iamge in the format RGBRGBRGB#
d = np.dstack(( img_r_array, img_g_array,img_b_array )).ravel()
d = d.reshape(phase_row_count,phase_row_count*3)

with open("myOutput.png", "wb") as out:
    pngWriter = png.Writer(
        phase_row_count, phase_row_count, greyscale=False, alpha=False, bitdepth=8
    )
    pngWriter.write(out, d)


