#UI Imports
from tkinter import scrolledtext
from tkinter import filedialog
from tkinter import *

#Main flow imports
from PIL import Image, ImageTk
from reedsolo import RSCodec
import numpy as np
import math
import png  #To read/write 16-bit sample images
import io   #For virtual files

#Set the bytes used for correction
rsc = RSCodec(13)


####Define Fourier functions####
def EncodePayload(image, payload, dump, logarithmic):

    ###############USER INPUTS###############
    fin = open(image, "rb")   #The image you want to edit
    DataIn = open(payload, "rb")
    output_intermediate_steps = dump #Should we show the intermediate steps? (Fourier domain images)
    ###############USER INPUTS END###############


    ################CONVERT TO FOURIER SPACE##################
    ###Open cover image and get dimensions###
    img_base = Image.open(fin)
    column_count, row_count = img_base.size


    ####Load each RGB channel from the image separately as greyscale####
    img_r, img_g, img_b = img_base.split()


    ####Perform Fourier transform on each channel####
    ###RED###
    red_f = np.fft.fft2(img_r)  #Do 2d FFT on image samples
    red_fshift = np.fft.fftshift(red_f) #Shift low freq to center for visualisation
    r_magnitude = np.abs(red_fshift)  #Magnitude information
    r_phase = np.angle(red_fshift)    #Phase information


    ###GREEN###
    green_f = np.fft.fft2(img_g)
    green_fshift = np.fft.fftshift(green_f)
    g_magnitude = np.abs(green_fshift)
    g_phase = np.angle(green_fshift)


    ###BLUE###
    blue_f = np.fft.fft2(img_b)
    blue_fshift = np.fft.fftshift(blue_f)
    b_magnitude = np.abs(blue_fshift)
    b_phase = np.angle(blue_fshift)


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


    #If we want to output the pre-edit Fourier space image do it here
    if(output_intermediate_steps):
        ###Scale each mag/phase array to the 48 bit image range###
        #For phase, shift from -pi, +pi to 0, +2pi instead of abs to preserve negatives
        #Divide by 2pi as that's the maximum value it could have
        phase_img_array_output = (phase_img_array+1*np.pi)/(2*np.pi)

        #For magnitude scale by N image pixels
        mag_img_array_output =  mag_img_array /(column_count*row_count)

        #Convert 0-1 values above to 0-65535 integers for 16-bit sample PNG
        phase_img_array_output = np.uint16(np.round( 65535*(phase_img_array_output) ))    #Casting doesn't round, do it ourselves to be more accurate
        mag_img_array_output = np.uint16(255*mag_img_array_output)

        #Should we log scale the output image?
        if(logarithmic):
            mag_img_array_output = np.uint16(np.clip((np.round(np.log(mag_img_array_output+1))*9000),0,65535))

        #Write the magnitude to the image file
        with open("Magnitude_pre_edit.png", "wb") as mag_png_file:
            pngWriter = png.Writer(
                column_count, row_count, greyscale=False, alpha=False, bitdepth=16
            )
            pngWriter.write(mag_png_file, mag_img_array_output)
            
        #Write the phase to the image file
        with open("phase.png", "wb") as phase_png_file:
            pngWriter = png.Writer(
                column_count, row_count, greyscale=False, alpha=False, bitdepth=16
            )
            pngWriter.write(phase_png_file, phase_img_array_output)



    #Find a suitable value to encode our payload with compared to the noise around middle where it's likely to be the largest:
    middle = math.floor((row_count*3)/2)
    maximumImageValue = (np.mean(mag_img_array[0][middle-20:middle+20]))
    additionValue = math.ceil(3.68*maximumImageValue + 13)  #Empirically tested values
    print("Using encoding value of:", additionValue)
    print("Encoding...")


    ################ADD PAYLOAD DATA TO THE FOURIER SPACE IMAGE##################
    image_2d = mag_img_array    #Copy to avoid overwriting


    #ECC Our input data
    ###################################
    PayloadData = DataIn.read()
    PayloadData = rsc.encode(bytearray(PayloadData))



    #Convert our data payload to binary bit string
    ###################################
    
    PayloadList = ""
    for i in range(0,len(PayloadData)):
        Temp = str(np.base_repr(PayloadData[i], base = 2, padding = 0).rjust(8,"0"))
        PayloadList += Temp

    #Add the length header to the start (4 bytes long)
    length_string = "{0:b}".format(len(PayloadList)).rjust(32, "0")
    PayloadList = length_string + PayloadList


    ###Set however many rows is necessary to hold our payload to black along the top and bottom (symmetry in space)###
    #Calculate how many rows our data needs
    rows_required = math.ceil((len(PayloadList)/3)/column_count)+6 #Add 6 for a buffer against any noise/quantization artifacts
        
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


    #Set the first row to the calibration 10101010... pattern
    for i in range(0,row_count*3):
        a = i + (2*column_count*3)
        x = a%(column_count*3)
        y = a//(column_count*3)
        currentValue = image_2d[y][x]
        if(i%2 == 0):   #Bit is 1
            image_2d[y][x] = currentValue + additionValue
            
    #Set our payload in the data of the top black section
    for i, payload_bit in enumerate(PayloadList):
        a = i + (3*column_count*3)
        x = a%(column_count*3)
        y = a//(column_count*3)
        currentValue = image_2d[y][x]
        if(payload_bit == "1"):   #Bit is 1
            image_2d[y][x] = currentValue + additionValue


    #If we want to output the post-edit Fourier space image do it here
    if(output_intermediate_steps):
        ###Scale each mag/phase array to the 48 bit image range###
        #For magnitude scale by N image pixels
        image_2d_output = image_2d/(column_count*row_count)
        image_2d_output = np.uint16(255*image_2d_output)

        #Should we log scale the output image?
        if(logarithmic):
            image_2d_output = np.uint16(np.clip((np.round(np.log(image_2d_output+1))*9000),0,65535))
    
        #Write the magnitude to the image file
        with open("Magnitude_post_edit.png", "wb") as mag_png_file:
            pngWriter = png.Writer(
                column_count, row_count, greyscale=False, alpha=False, bitdepth=16
            )
            pngWriter.write(mag_png_file, image_2d_output)



    ################DO THE INVERSE FOURIER TO GET THE FINAL IMAGE WITH PAYLOAD INSIDE##################
    phase_image_2d = phase_img_array
    phase_image_2d = np.concatenate(phase_image_2d)
   
    mag_image_2d = image_2d
    mag_image_2d = np.concatenate(mag_image_2d)


    #Seperate the image data into [RRR],[BBB],[GGG] instead of RGBRGBRGBRGB for seperate treatment
    mag_image_r = mag_image_2d[0::3]
    mag_image_g = mag_image_2d[1::3]
    mag_image_b = mag_image_2d[2::3]

    phase_image_r = phase_image_2d[0::3]
    phase_image_g = phase_image_2d[1::3]
    phase_image_b = phase_image_2d[2::3]



    #Combine these into an array of complex numbers for each channel#
    red_fshift = (mag_image_r*np.exp(1j*phase_image_r)).reshape(row_count,column_count)
    green_fshift = (mag_image_g*np.exp(1j*phase_image_g)).reshape(row_count,column_count)
    blue_fshift = (mag_image_b*np.exp(1j*phase_image_b)).reshape(row_count,column_count)


    #Unshift these back to original numpy order#
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



def DecodeImage(image, log, logarithmic):
    ###############USER INPUTS###############
    fin = open(image, "rb")    #The image to read
    output_intermediate_steps = log #Should we show the intermediate steps? (Fourier domain images)
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

        #Should we log scale the output image?
        if(logarithmic):
            mag_img_array = np.uint16(np.clip((np.round(np.log(mag_img_array+1))*9000),0,65535))
 

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
    print("Extracting payload...")

    #Figure our the boundary values using the calibration header
    LowArray = []
    HighArray = []
    for i in range(0,row_count*3):
        a = i + (2*column_count*3)
        x = a%(column_count*3)
        y = a//(column_count*3)
        currentValue = image_2d[y][x]
        if(i%2 == 0):   #Bit is 1
            LowArray.append(currentValue)
        else:
            HighArray.append(currentValue)

    #We assume that a 1 bit will always have a value at least of HighBitBounday
    HighBitBounday = math.floor(np.min(LowArray))


    print("Decoding high bit boundary value:",HighBitBounday)


    #Crop the start and end of payload
    #The payload will only start after 2 rows and never be more than half of the height so crop it to those
    payload_array = (image_2d.flatten())[ 3*column_count*3 : int((column_count/2)*column_count*3) ]
    Decoded_Payload_Binary = ((payload_array>=HighBitBounday).astype(int))

    #Convert to string to get length header
    payload_string = ""
    for bit in Decoded_Payload_Binary:
        if(bit==1):
            payload_string+="1"
        else:
            payload_string+="0"

    #Read length header
    end_index = int(payload_string[0:32], 2)+32 #+32 to account for actual size of 4 byte length header itself

    #Actually crop off end section now and convert to bytearray for final file
    Decoded_Payload_Binary = Decoded_Payload_Binary[32:end_index]    
    payload_bytearray = bytearray(np.packbits(Decoded_Payload_Binary))

    #Decode the ECC
    try:
        payload_bytearray = rsc.decode(payload_bytearray)[0]
    except:
        print("Too many errors to fully correct, outputting raw data")    #Too many errors, just output the raw data

    #Write the extracted payload to a file 
    with open("ExtractedPayload.txt","wb") as fout:
        fout.write(payload_bytearray)
    print("Finished decoding")


####Define GUI functions####
def LoadImage(*args):   #Let the user choose the cover image file
    global Img_In_Path
    Img_In_Path=filedialog.askopenfilename(filetypes=[("Image File",'.png')])
    #Attempt to load the file selected
    try:
        im = Image.open(Img_In_Path)
        img = ImageTk.PhotoImage(im.resize((300,300), Image.ANTIALIAS))

        panel = Label(TopIO, image=img)
        panel.image = img
        panel.place(relheight=1,relwidth=1,relx=1,rely=0.2)
        panel.grid(column=0,row=0, padx=(30,0),pady=0)
    except:
        print("Unsupported / not selected file")


def LoadPayload(*args):   #Let the user choose the cover image file
    global Payload_In_Path 
    Payload_In_Path = filedialog.askopenfilename()
    payload_data = open(Payload_In_Path, "rb")



####GUI Code####
####Initalise window####
window = Tk()
window.title("Fourier Steg")
window.geometry("370x560")


####Create sections and layout format####
TopIO = Frame(window, width=300, height = 300)
TopIO.grid(row=0, column=0, sticky='nwew', padx=0, pady=20)

MiddleIO = Frame(window)
MiddleIO.grid(row=1, column=0, sticky='nsew', padx=130, pady=(0,10))

BottomIO = Frame(window)
BottomIO.grid(row=2, column=0, sticky='nsew')


BottomIOLeft = Frame(BottomIO)
BottomIOLeft.grid(row=0, column=0, sticky='nsew')

BottomIORight = Frame(BottomIO)
BottomIORight.grid(row=0, column=1, sticky='nsew')


####Labels####
encodeSectionLBL = Label(BottomIOLeft, text="Encoding", font='Helvetica 14')
encodeSectionLBL.grid(column=0, row=0, pady = (0,3))

decodeSectionLBL = Label(BottomIORight, text="Decoding", font='Helvetica 14')
decodeSectionLBL.grid(column=0, row=0, pady = (0,3))

####Buttons####
BTN_loadImg = Button(MiddleIO, text="Load Image", command=LoadImage)
BTN_loadImg.grid(column=0,row=0, padx=10)


BTN_loadPayload = Button(BottomIOLeft, text="Load Payload", command=LoadPayload)
BTN_loadPayload.grid(column=0,row=1, padx=10, pady=3)

BTN_encodePayload = Button(BottomIOLeft, text="Encode Payload", command=lambda:EncodePayload(Img_In_Path, Payload_In_Path, Encode_Log.get(), Encode_Log_Scaled.get()))
BTN_encodePayload.grid(column=0,row=2, padx=10, pady=3)




BTN_decodePayload = Button(BottomIORight, text="Decode Image", command=lambda:DecodeImage(Img_In_Path, Decode_Log.get(), Decode_Log_Scaled.get()))
BTN_decodePayload.grid(column=0,row=1, padx=10)

####Tickboxes####
##Dump intermediate steps###
Encode_Log = IntVar()
TickBX_Encode_Log = Checkbutton(BottomIOLeft, text = "Dump intermediate steps", variable = Encode_Log, selectcolor="black")
TickBX_Encode_Log.select()
TickBX_Encode_Log.grid(column=0,row=3, padx=10)

Decode_Log = IntVar()
TickBX_Decode_Log = Checkbutton(BottomIORight, text = "Dump intermediate steps", variable = Decode_Log, selectcolor="black")
TickBX_Decode_Log.select()  #Set on as default
TickBX_Decode_Log.grid(column=0,row=2, padx=10)

##Logarithmic scaling?###
Encode_Log_Scaled = IntVar()
TickBX_Encode_Log_Scaled = Checkbutton(BottomIOLeft, text = "Log scaling?", variable = Encode_Log_Scaled, selectcolor="black")
TickBX_Encode_Log_Scaled.select()
TickBX_Encode_Log_Scaled.grid(column=0,row=4, padx=10)

Decode_Log_Scaled = IntVar()
TickBX_Decode_Log_Scaled = Checkbutton(BottomIORight, text = "Log scaling?", variable = Decode_Log_Scaled, selectcolor="black")
TickBX_Decode_Log_Scaled.select()  #Set on as default
TickBX_Decode_Log_Scaled.grid(column=0,row=3, padx=10)


####Section Styling####
window['highlightcolor']='#212121'
window['background']='#212121'
TopIO['background']='#212121'
MiddleIO['background']='#212121'
BottomIO['background']='#333333'
BottomIOLeft['background']='#333333'
BottomIORight['background']='#333333'

#Labels
encodeSectionLBL['background']='#333333'
encodeSectionLBL['foreground']='#FFFFFF'

decodeSectionLBL['background']='#333333'
decodeSectionLBL['foreground']='#FFFFFF'

#Tickboxes
TickBX_Encode_Log['background']='#333333'
TickBX_Encode_Log['foreground']='#FFFFFF'
TickBX_Decode_Log['background']='#333333'
TickBX_Decode_Log['foreground']='#FFFFFF'

TickBX_Encode_Log_Scaled['background']='#333333'
TickBX_Encode_Log_Scaled['foreground']='#FFFFFF'
TickBX_Decode_Log_Scaled['background']='#333333'
TickBX_Decode_Log_Scaled['foreground']='#FFFFFF'


####Main loop####
window.mainloop() 
