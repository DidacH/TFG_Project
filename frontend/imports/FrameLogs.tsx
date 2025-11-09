// import {Download} from "lucide-react";





// export default function FrameLogs(){

//     const [downloading, setDownloading] = useState<'users' | 'logs' | null>(null);

//     //Manage CSV Download
//     const handleDownload = async (type: 'users' | 'logs') => {
//         setDownloading(type);
//         const token = getToken();
//         try {
//             const response = await fetch(`${API_URL}/api/admin/${type}/download`, {
//                 headers: { 'Authorization': `Bearer ${token}` },
//             });
//             if (!response.ok) throw new Error('Download failed');

//             //Obtain filename based on type
//             const filename = type === 'users' ? 'users.csv' : 'logs.csv';
            
//             //Create blob and trigger download
//             const blob = await response.blob();
//             const url = window.URL.createObjectURL(blob);
//             const a = document.createElement('a');
//             a.href = url;
//             a.download = filename;
//             document.body.appendChild(a);
//             a.click();
//             a.remove();
//             window.URL.revokeObjectURL(url);

//         } catch (err: any) {
//             setError(`Failed to download ${type}.csv`);
//         } finally {
//             setDownloading(null);
//         }
//     };

//     return();
// }