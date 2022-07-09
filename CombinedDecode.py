from PIL import Image
import numpy as np
import struct   #Decode binary string
import math
import png  #To read/write 16-bit sample images
import io   #For virtual files

##################Basic breakdown##################
'''
Decoding the image involves taking the Fourier transform of the image
and reading off the RGB values in the magnitude image. For each channel
if its value is over a threshold it's trated as a 1 bit, otherwise if it's
beneath it's a 0 bit.
'''

###############USER INPUTS###############
fin = open("ImageWithPayload.png", "rb")    #The image to read
output_intermediate_steps = True #Should we show the intermediate steps? (Fourier domain images)
###############USER INPUTS END###############



################CONVERT TO FOURIER SPACE##################
###Getting image dimensions###
img_base = Image.open(fin)
column_count, row_count = img_base.size

####Load each RGB channel from the image as greyscale####
img_r, img_g, img_b = img_base.split()


####Perform fourier transform on each channel####
###RED###
red_f = np.fft.fft2(img_r)
red_fshift = np.fft.fftshift(red_f) #Shift low freq to center for visualisation
red_magnitude = np.abs(red_fshift)
red_phase = np.angle(red_fshift)


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
#For phase shift from -pi, +pi to 0, +2pi instead of abs to preserve
r_phase = (red_phase+1*np.pi)/(2*np.pi)
g_phase = (green_phase+1*np.pi)/(2*np.pi)
b_phase = (blue_phase+1*np.pi)/(2*np.pi)

#For mag scale by N image pixels
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

#Dump Fourier space images if selected
if(output_intermediate_steps):
    #Write the phase to a temp file
    phase_png_file_output = open("Phase_Decoded.png", "wb")
    pngWriter = png.Writer(
        column_count, row_count, greyscale=False, alpha=False, bitdepth=16
    )
    pngWriter.write(phase_png_file_output, phase_img_array)


    #Write the magnitude to a temp file
    mag_png_file_output = open("Magnitude_Decoded.png", "wb")
    pngWriter = png.Writer(
        column_count, row_count, greyscale=False, alpha=False, bitdepth=16
    )
    pngWriter.write(mag_png_file_output, mag_img_array)

    #Seek to the start of both files so we can open them later
    phase_png_file.seek(0)
    mag_png_file.seek(0)
    phase_png_file_output.close()
    mag_png_file_output.close()
    


################READ DATA FROM FOURIER SPACE IMAGE##################
#Get image data from above magnitude file
file = mag_png_file
pngReader=png.Reader(file)

row_count, column_count, pngdata, meta = pngReader.asDirect()
image_2d = np.vstack(list(map(np.uint16, pngdata)))

#Read the actual data
payload_data = ""
currentWindow = np.array([1,1,1,1,1,1,1,1])   #Temp start it as all 1s
#currentWindow is to keep track of the history of bits so if we're just getting 0 over
#and over again then we've reached the end of the file


#Read all pixels until we get 8 0's in a row, indicating the end of data
print("Extracting payload...")
for i in range((2*column_count*3),column_count*row_count*3):
    #print(currentWindow)
    if(np.sum(currentWindow)!=0):   #If we're not at the end of our payload then keep going
        x = i%(column_count*3)
        y = i//(column_count*3)

        #Check the current value
        currentValue = image_2d[y][x]
        if(currentValue>4):
            payload_data += "1" #1 Bit
            currentWindow = np.delete(currentWindow, 0) #Remove oldest bit and add 1
            currentWindow = np.append(currentWindow, 1)
        elif(currentValue<5):
            payload_data += "0" #0 Bit
            currentWindow = np.delete(currentWindow, 0) #Remove oldest bit and add 0
            currentWindow = np.append(currentWindow, 0)
    

#Convert our bitstring payload to bytes
i = 0
output_bytes = bytearray()
while i < len(payload_data):
    output_bytes.append(int(payload_data[i:i+8], 2))
    i += 8

#Write the extracted payload to a file 
with open("ExtractedPayload.txt","wb") as fout:
    fout.write(output_bytes)
