import axios from "axios";

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL,
  headers: {
    "Content-Type": "application/json",
  },
});

export const uploadFile = async (endpoint: string, formData: FormData) => {
  return api.post(endpoint, formData, {
    headers: {
      "Content-Type": "application/form-data",
    },
  });
};

export default api;
