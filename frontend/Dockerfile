FROM node:lts-alpine

WORKDIR /app

# Copy package.json and lock file
COPY package*.json ./

# Install dependencies
RUN npm install

# Copy the rest of the application source code
COPY . .

# The command to run the development server
CMD ["npm", "run", "dev" , "--", "--host"]