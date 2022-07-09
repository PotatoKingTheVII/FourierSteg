from PIL import Image
import numpy as np
import math
import png  #To read/write 16-bit sample images
import io   #For virtual files

##################Basic breakdown##################
'''
The basic flow takes the cover image in, converts it to Fourier space
as an image, writes black to the top and bottom (symmetry in Fourier space)
enough to contain the payload. It then encodes the payload's bits in each
RGB channel using the minimum value that is preserved after quantization to
ensure it affects the image as little as possible. Then this edited magnitude
Fourier component is decoded using the inverse Fourier transform to get our
edited image with the payload inside.

The cover image ***must be square and have even resolution on both axis.***
Imagemagick has the same limitations and just stretches images such that
they're square. I think this is due to the maths from the Fourier itself.


Note that to see detail in the Fourier domain images you'll need
to change the RGB curves in something that can display full 48-bit
pixel images (GIMP works)
'''

###############USER INPUTS###############
fin = open("ImageInput.png", "rb")   #The image you want to edit
TextIn = "Hello World! This is a test to check how well the embedding works in Fourier space assuming we edit a decent amount of pixels"*10 #The payload to hide
output_intermediate_steps = True #Should we show the intermediate steps? (Fourier domain images)
###############USER INPUTS END###############


################CONVERT TO FOURIER SPACE##################
###Open cover image and get dimensions###
img_base = Image.open(fin)
column_count, row_count = img_base.size


####Load each RGB channel from the image separately as greyscale####
img_r, img_g, img_b = img_base.split()


####Perform fourier transform on each channel####
###RED###
red_f = np.fft.fft2(img_r)  #Do 2d FFT on image samples
red_fshift = np.fft.fftshift(red_f) #Shift low freq to center for visualisation
red_magnitude = np.abs(red_fshift)  #Magnitude information
red_phase = np.angle(red_fshift)    #Phase information


###GREEN###
green_f = np.fft.fft2(img_g)
green_fshift = np.fft.fftshift(green_f)
green_magnitude = np.abs(green_fshift)
green_phase = np.angle(green_fshift)


###BLUE###
blue_f = np.fft.fft2(img_b)
blue_fshift = np.fft.fftshift(blue_f)
blue_magnitude = np.abs(blue_fshift)
blue_phase = np.angle(blue_fshift)




###Scale each mag/phase array to the 48 bit image range###
#For phase, shift from -pi, +pi to 0, +2pi instead of abs to preserve negatives
#Divide by 2pi as that's the maximum value it could have
r_phase = (red_phase+1*np.pi)/(2*np.pi)
g_phase = (green_phase+1*np.pi)/(2*np.pi)
b_phase = (blue_phase+1*np.pi)/(2*np.pi)

#For magnitude scale by N image pixels
r_magnitude = red_magnitude/(column_count*row_count)
g_magnitude = green_magnitude/(column_count*row_count)
b_magnitude = blue_magnitude/(column_count*row_count)


#Convert 0-1 values above to 0-65535 integers for 16-bit sample PNG
r_phase = np.uint16(np.round( 65535*(r_phase) ))    #Casting doesn't round, do it ourselves to be more accurate
g_phase = np.uint16(np.round( 65535*(g_phase) ))
b_phase = np.uint16(np.round( 65535*(b_phase) ))

r_magnitude = np.uint16(255*r_magnitude)
g_magnitude = np.uint16(255*g_magnitude)
b_magnitude = np.uint16(255*b_magnitude)



#Transpose to fix orientation of resulting image
r_phase = r_phase.T
g_phase = g_phase.T
b_phase = b_phase.T

r_magnitude = r_magnitude.T
g_magnitude = g_magnitude.T
b_magnitude = b_magnitude.T


#Combine the seperate R,G,B channels to form final images
phase_img_array = np.dstack( (r_phase, g_phase, b_phase) )
phase_img_array = np.hstack(phase_img_array)

mag_img_array = np.dstack( (r_magnitude, g_magnitude, b_magnitude) )
mag_img_array = np.hstack(mag_img_array)



#Write the phase to a temp file
phase_png_file = io.BytesIO()
pngWriter = png.Writer(
    column_count, row_count, greyscale=False, alpha=False, bitdepth=16
)
pngWriter.write(phase_png_file, phase_img_array)


#Write the magnitude to a temp file
mag_png_file = io.BytesIO()
pngWriter = png.Writer(
    column_count, row_count, greyscale=False, alpha=False, bitdepth=16
)
pngWriter.write(mag_png_file, mag_img_array)

#Seek to the start of both files so we can open them later
phase_png_file.seek(0)
mag_png_file.seek(0)

#If we want to output Fourier steps write them to file
if(output_intermediate_steps):
    #Write the phase to a temp file
    phase_png_file_output = open("Phase.png", "wb")
    pngWriter = png.Writer(
        column_count, row_count, greyscale=False, alpha=False, bitdepth=16
    )
    pngWriter.write(phase_png_file_output, phase_img_array)


    #Write the magnitude to a temp file
    mag_png_file_output = open("Magnitude_pre_edit.png", "wb")
    pngWriter = png.Writer(
        column_count, row_count, greyscale=False, alpha=False, bitdepth=16
    )
    pngWriter.write(mag_png_file_output, mag_img_array)

    #Close the files and seek back to the start
    phase_png_file_output.close()
    mag_png_file_output.close()
    phase_png_file.seek(0)
    mag_png_file.seek(0)



################ADD PAYLOAD DATA TO THE FOURIER SPACE IMAGE##################
#Load the temp magnitude file from above and get its size and pixels
file = mag_png_file
pngReader=png.Reader(file)
row_count, column_count, pngdata, meta = pngReader.asDirect()
image_2d = np.vstack(list(map(np.uint16, pngdata)))


#Convert payload text to binary string
###################################
TextList = ""
for i in range(0,len(TextIn)):
    Temp = str(np.base_repr(ord(TextIn[i]), base = 2, padding = 0).rjust(8,"0"))
    TextList += Temp


###Set however many rows is necessary to hold our payload to black along the top and bottom (symmetry in space)###
#Calculate how many rows our data needs
rows_required = math.ceil((len(TextList)/3)/column_count)+6 #Add 6 for a buffer against any noise/quantization artifacts
    
#Set the top rows_required to 0,0,0 (black/empty)
for i in range(0,rows_required*(column_count*3)):
    x = i%(column_count*3)
    y = i//(column_count*3)

    if(i%6<=2):
        image_2d[y][x] = 0
    else:
        image_2d[y][x] = 0



#Set the bottom rows_required to 0,0,0 (black/empty)
for i in range((row_count*column_count*3)-1,(row_count*column_count*3)-rows_required*(column_count*3),-1):
    x = i%(column_count*3)
    y = i//(column_count*3)
    if(i%6<=2):
        image_2d[y][x] = 0
    else:
        image_2d[y][x] = 0


#Set our payload in the data of the top black section
for i, payload_bit in enumerate(TextList):
    a = i + (2*column_count*3)
    x = a%(column_count*3)
    y = a//(column_count*3)
    currentValue = image_2d[y][x]
    if(payload_bit == "1"):   #Bit is 1
        image_2d[y][x] = currentValue + 13  #+13 is the minimum after which the data survives quantization


#Write the edited magnitude with our payload to a temp file
mag_img_with_payload = io.BytesIO()
pngWriter = png.Writer(
    column_count, row_count, greyscale=False, alpha=False, bitdepth=16
)
pngWriter.write(mag_img_with_payload, image_2d)
mag_img_with_payload.seek(0)    #Seek to start of file to read later


if(output_intermediate_steps):
    mag_img_with_payload_output = open("Magnitude_post_edit.png", "wb")
    pngWriter = png.Writer(
        column_count, row_count, greyscale=False, alpha=False, bitdepth=16
    )
    pngWriter.write(mag_img_with_payload_output, image_2d)
    mag_img_with_payload_output.close()
    mag_img_with_payload.seek(0)    #Seek to start of file to read later


################DO THE INVERSE FOURIER TO GET THE FINAL IMAGE WITH PAYLOAD INSIDE##################
####Load our edited fourier space files from above####
fin_phase = phase_png_file
fin_mag = mag_img_with_payload


####Load each RGB channel from the image as greyscale####
pngReader_phase = png.Reader(fin_phase)
pngReader_mag = png.Reader(fin_mag)

phase_row_count, phase_column_count, phase_pngdata, phase_meta = pngReader_phase.asDirect()
phase_image_2d = np.vstack(list(map(np.uint16, phase_pngdata)))
phase_image_2d = np.concatenate(phase_image_2d)


mag_row_count, mag_column_count, mag_pngdata, mag_meta = pngReader_mag.asDirect()
mag_image_2d = np.vstack(list(map(np.uint16, mag_pngdata)))
mag_image_2d = np.concatenate(mag_image_2d)


#Seperate the image data into [RRR],[BBB],[GGG] instead of RGBRGBRGBRGB for seperate treatment
mag_image_r = mag_image_2d[0::3]
mag_image_g = mag_image_2d[1::3]
mag_image_b = mag_image_2d[2::3]

phase_image_r = phase_image_2d[0::3]
phase_image_g = phase_image_2d[1::3]
phase_image_b = phase_image_2d[2::3]

#Scale these values back to their originals from the compressed 16 bit image space:
mag_image_r = (row_count*column_count)*(mag_image_r/255)
mag_image_g = (row_count*column_count)*(mag_image_g/255)
mag_image_b = (row_count*column_count)*(mag_image_b/255)

phase_image_r = (2*np.pi*(phase_image_r/65535)) - np.pi
phase_image_g = (2*np.pi*(phase_image_g/65535)) - np.pi
phase_image_b = (2*np.pi*(phase_image_b/65535)) - np.pi

#Combine these into an array of complex numbers for each channel#
red_fshift = (mag_image_r*np.exp(1j*phase_image_r)).reshape(row_count,column_count)
green_fshift = (mag_image_g*np.exp(1j*phase_image_g)).reshape(row_count,column_count)
blue_fshift = (mag_image_b*np.exp(1j*phase_image_b)).reshape(row_count,column_count)


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
#Otherwise due to quantization errors it could be outside the range
img_r_array = np.uint8(np.clip(np.round(np.abs(img_r_array.real)),0,255))
img_g_array = np.uint8(np.clip(np.round(np.abs(img_g_array.real)),0,255))
img_b_array = np.uint8(np.clip(np.round(np.abs(img_b_array.real)),0,255))

#Merge the seperate RGB channels together for the final image in the format RGBRGBRGB#
img_rgb = np.dstack(( img_r_array, img_g_array,img_b_array )).ravel()
img_rgb = img_rgb.reshape(column_count,row_count*3)

#Write the combined RGB channels to the final payload image
with open("ImageWithPayload.png", "wb") as out:
    pngWriter = png.Writer(
        row_count, column_count, greyscale=False, alpha=False, bitdepth=8
    )
    pngWriter.write(out, img_rgb)


print("Finished...")

